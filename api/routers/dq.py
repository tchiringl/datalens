"""
Data Quality router with frontend-compatible response shape.

Primary source:
- OpenMetadata test cases (when configured)

Fallback source:
- dbt store-failures tables in postgres.dbt_test__audit
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.om_client import OpenMetadataClient, get_om_client
from services.trino_client import TrinoClient

router = APIRouter()


class DQResult(BaseModel):
    id: str
    model: str
    column_name: Optional[str] = None
    test_type: str
    status: Literal["pass", "fail", "warn", "error"]
    failures: int
    warn_count: int = 0
    execution_time: float = 0.0
    last_run: datetime
    message: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_entity_link(entity_link: str) -> Dict[str, str]:
    result = {"table": "", "column": ""}
    if not entity_link:
        return result
    inner = entity_link.strip("<>").removeprefix("#E::")
    parts = inner.split("::")
    if len(parts) >= 2:
        result["table"] = parts[1]
    if len(parts) >= 4 and parts[2].lower() == "columnname":
        result["column"] = parts[3]
    return result


def _infer_test_type(name: str) -> str:
    lower = name.lower()
    if "not_null" in lower or "notnull" in lower:
        return "not_null"
    if "unique" in lower:
        return "unique"
    if "relationship" in lower:
        return "relationships"
    if "accepted_values" in lower:
        return "accepted_values"
    return "custom"


def _status_from_om(status: Optional[str]) -> Literal["pass", "fail", "warn", "error"]:
    if status == "Success":
        return "pass"
    if status == "Failed":
        return "fail"
    if status == "Aborted":
        return "error"
    return "warn"


def _table_to_model(table_fqn: str, default: str = "unknown_model") -> str:
    if not table_fqn:
        return default
    tail = table_fqn.split(".")[-1]
    return tail or default


async def _results_from_openmetadata() -> List[DQResult]:
    om = get_om_client()
    test_cases = await om.get_dq_results()
    results: List[DQResult] = []

    for tc in test_cases:
        latest = tc.get("testCaseResult")
        if not latest:
            continue

        entity_link = tc.get("entityLink", "")
        parsed = _parse_entity_link(entity_link)
        table_fqn = parsed["table"]
        column = parsed["column"] or None

        ts_ms = latest.get("timestamp")
        last_run = _now()
        if ts_ms:
            try:
                last_run = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            except Exception:
                pass

        test_name = tc.get("name", tc.get("fullyQualifiedName", "unknown_test"))
        failures_val = latest.get("failedRows") or latest.get("value") or 0
        try:
            failures = int(failures_val)
        except Exception:
            failures = 0

        results.append(
            DQResult(
                id=str(tc.get("id", test_name)),
                model=_table_to_model(table_fqn),
                column_name=column,
                test_type=_infer_test_type(test_name),
                status=_status_from_om(latest.get("testCaseStatus")),
                failures=failures,
                warn_count=0,
                execution_time=0.0,
                last_run=last_run,
                message=latest.get("result"),
            )
        )

    return results


def _extract_model_from_failure_table(table_name: str) -> str:
    # e.g. relationships_fact_orders_... -> fact_orders
    tokens = table_name.split("_")
    for i, token in enumerate(tokens):
        if token in {"dim", "fact", "stg"} and i + 1 < len(tokens):
            return f"{token}_{tokens[i + 1]}"
    # fallback to first 2 tokens
    if len(tokens) >= 2:
        return f"{tokens[0]}_{tokens[1]}"
    return table_name


def _test_type_from_failure_table(table_name: str) -> str:
    lower = table_name.lower()
    if lower.startswith("not_null"):
        return "not_null"
    if lower.startswith("unique"):
        return "unique"
    if lower.startswith("relationships"):
        return "relationships"
    if lower.startswith("accepted_values"):
        return "accepted_values"
    return "custom"


def _results_from_dbt_store_failures() -> List[DQResult]:
    trino = TrinoClient()
    try:
        table_names = trino.list_tables("postgres", "dbt_test__audit")
    except Exception:
        return []

    results: List[DQResult] = []
    for tbl in table_names:
        try:
            count = trino.get_table_row_count("postgres", "dbt_test__audit", tbl)
        except Exception:
            count = -1
        failures = max(0, count)
        status: Literal["pass", "fail", "warn", "error"] = "fail" if failures > 0 else "pass"
        results.append(
            DQResult(
                id=f"dbt_audit::{tbl}",
                model=_extract_model_from_failure_table(tbl),
                column_name=None,
                test_type=_test_type_from_failure_table(tbl),
                status=status,
                failures=failures,
                warn_count=0,
                execution_time=0.0,
                last_run=_now(),
                message=f"dbt store-failures table: dbt_test__audit.{tbl}",
            )
        )
    return results


async def _load_results() -> List[DQResult]:
    try:
        om_results = await _results_from_openmetadata()
        if om_results:
            return om_results
    except Exception:
        pass
    return _results_from_dbt_store_failures()


@router.get("/results", response_model=List[DQResult], summary="All DQ test results")
async def get_all_dq_results() -> List[DQResult]:
    return await _load_results()


@router.get("/summary", summary="Aggregate DQ summary")
async def get_dq_summary() -> Dict[str, Any]:
    results = await _load_results()
    total = len(results)
    passing = sum(1 for r in results if r.status == "pass")
    failing = sum(1 for r in results if r.status == "fail")
    warnings = sum(1 for r in results if r.status == "warn")

    by_type: Dict[str, Dict[str, int]] = {}
    by_model: Dict[str, Dict[str, int]] = {}
    for r in results:
        by_type.setdefault(r.test_type, {"pass": 0, "fail": 0})
        by_model.setdefault(r.model, {"pass": 0, "fail": 0})
        if r.status == "pass":
            by_type[r.test_type]["pass"] += 1
            by_model[r.model]["pass"] += 1
        else:
            by_type[r.test_type]["fail"] += 1
            by_model[r.model]["fail"] += 1

    pass_rate = round((passing / total * 100), 1) if total else 0.0
    return {
        "total_tests": total,
        "passing": passing,
        "failing": failing,
        "warnings": warnings,
        "pass_rate": pass_rate,
        "by_type": by_type,
        "by_model": by_model,
    }


@router.get("/issues", response_model=List[DQResult], summary="Failing tests only")
async def get_dq_issues() -> List[DQResult]:
    results = await _load_results()
    return [r for r in results if r.status in {"fail", "warn", "error"}]

