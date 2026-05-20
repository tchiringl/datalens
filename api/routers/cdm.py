"""
CDM (Common Data Model) router.

Endpoints
---------
GET /api/cdm/models           list all CDM models (dim_*, fact_*)
GET /api/cdm/models/{name}    model details: columns, row count, last updated
GET /api/cdm/lineage/{table}  upstream + downstream lineage for a CDM table
GET /api/cdm/stats            summary stats: total rows per table
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routers._pagination import pagination
from services.om_client import OpenMetadataClient, get_om_client
from services.trino_client import TrinoClient

router = APIRouter()

# Trino catalog / schema where CDM (dbt-generated) models live
# POC currently materializes into the postgres connector.
CDM_CATALOG = "postgres"
CDM_SCHEMA = "cdm"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CDMColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    description: Optional[str] = None
    dq_status: Optional[str] = None


class CDMModelDetail(BaseModel):
    name: str
    schema: str
    materialization: str
    description: str
    row_count: Optional[int] = None
    columns: List[CDMColumnInfo] = []
    last_updated: Optional[datetime] = None
    tags: List[str] = []
    depends_on: List[str] = []


class CDMStats(BaseModel):
    total_models: int
    total_rows: int
    models: List[Dict[str, Any]]
    last_updated: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_model(name: str) -> str:
    lower = name.lower()
    if lower.startswith("dim_"):
        return "dimension"
    if lower.startswith("fact_"):
        return "fact"
    return "other"


async def _get_cdm_table_names(trino: TrinoClient) -> List[str]:
    """Return all table names in the CDM schema from Trino."""
    loop = asyncio.get_event_loop()
    try:
        tables = await loop.run_in_executor(None, trino.list_tables, CDM_CATALOG, CDM_SCHEMA)
        return tables
    except Exception:
        return []


async def _get_row_count(trino: TrinoClient, table: str) -> Optional[int]:
    loop = asyncio.get_event_loop()
    try:
        count = await loop.run_in_executor(
            None, trino.get_table_row_count, CDM_CATALOG, CDM_SCHEMA, table
        )
        return count if count >= 0 else None
    except Exception:
        return None


async def _get_columns(trino: TrinoClient, table: str) -> List[CDMColumnInfo]:
    loop = asyncio.get_event_loop()
    try:
        raw_cols = await loop.run_in_executor(
            None, trino.get_table_columns, CDM_CATALOG, CDM_SCHEMA, table
        )
        return [
            CDMColumnInfo(
                name=col.get("name", ""),
                data_type=col.get("type", ""),
                nullable=col.get("nullable", True),
                description=col.get("comment") or None,
            )
            for col in raw_cols
        ]
    except Exception:
        return []


def _om_table_to_last_updated(om_table: Optional[Dict[str, Any]]) -> Optional[datetime]:
    if not om_table:
        return None
    ts_ms = om_table.get("updatedAt")
    if ts_ms:
        try:
            return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        except Exception:
            return None
    return None


def _materialization_for(name: str) -> str:
    return "incremental" if name.lower().startswith("fact_") else "table"


def _tags_for(name: str) -> List[str]:
    cls = _classify_model(name)
    if cls == "dimension":
        return ["dimension"]
    if cls == "fact":
        return ["fact"]
    return ["model"]


def _load_dq_status_map(trino: TrinoClient) -> Dict[str, Dict[str, Any]]:
    """
    Build {model_name: {column_name: status, "__model__": status}} from dbt test failures.

    Status values are: pass | fail | warn.
    """
    dq_map: Dict[str, Dict[str, Any]] = {}
    try:
        audit_tables = trino.list_tables("postgres", "dbt_test__audit")
    except Exception:
        return dq_map

    for test_tbl in audit_tables:
        failures = trino.get_table_row_count("postgres", "dbt_test__audit", test_tbl)
        if failures <= 0:
            continue

        parts = test_tbl.split("_")
        if len(parts) < 3:
            continue

        prefix = parts[0]
        model: Optional[str] = None
        column: Optional[str] = None

        # Typical patterns:
        # - not_null_fact_orders_order_id
        # - unique_dim_products_sku
        # - accepted_values_dim_customers_<hash>
        # - relationships_fact_orders_<hash>
        if prefix in {"not", "notnull", "unique", "accepted", "acceptedvalues", "relationships"}:
            # Not expected due to underscore splitting of not_null/accepted_values;
            # keep fallback behavior below.
            pass

        if test_tbl.startswith("not_null_") or test_tbl.startswith("unique_"):
            # e.g. not_null_fact_orders_order_id
            body = test_tbl.split("_", 2)[2]  # fact_orders_order_id
            body_parts = body.split("_")
            if len(body_parts) >= 3 and body_parts[0] in {"dim", "fact", "stg"}:
                model = f"{body_parts[0]}_{body_parts[1]}"
                column = "_".join(body_parts[2:])
        elif test_tbl.startswith("accepted_values_"):
            body = test_tbl.split("_", 2)[2]  # dim_customers_<hash...>
            body_parts = body.split("_")
            if len(body_parts) >= 2 and body_parts[0] in {"dim", "fact", "stg"}:
                model = f"{body_parts[0]}_{body_parts[1]}"
        elif test_tbl.startswith("relationships_"):
            body = test_tbl.split("_", 1)[1]
            body_parts = body.split("_")
            if len(body_parts) >= 2 and body_parts[0] in {"dim", "fact", "stg"}:
                model = f"{body_parts[0]}_{body_parts[1]}"
                # Sometimes includes explicit column in pattern relationships_fact_orders_store_id...
                if len(body_parts) >= 3 and body_parts[2] not in {"ref", "to"}:
                    # If token looks like a hash, treat as model-level issue instead.
                    token = body_parts[2]
                    if len(token) >= 12 and all(ch in "0123456789abcdef" for ch in token.lower()):
                        column = None
                    else:
                        column = token
        elif test_tbl.startswith("dbt_utils_expression_is_true_"):
            # Often hashed/sanitized; treat as model-level warning if model can be inferred.
            for prefix_model in ("dim_", "fact_", "stg_"):
                idx = test_tbl.find(prefix_model)
                if idx >= 0:
                    tail = test_tbl[idx:]
                    seg = tail.split("_")
                    if len(seg) >= 2:
                        model = f"{seg[0]}_{seg[1]}"
                    break

        if not model:
            continue

        model_map = dq_map.setdefault(model, {"columns": {}, "reasons": set()})
        col_map: Dict[str, str] = model_map["columns"]
        reason_set: Set[str] = model_map["reasons"]
        if column:
            col_map[column.lower()] = "fail"
        else:
            # model-level test failure with no resolvable column
            reason_set.add(_test_type_prefix(test_tbl))

    return dq_map


def _test_type_prefix(test_table_name: str) -> str:
    if test_table_name.startswith("relationships_"):
        return "relationships"
    if test_table_name.startswith("accepted_values_"):
        return "accepted_values"
    if test_table_name.startswith("dbt_utils_expression_is_true_"):
        return "expression"
    if test_table_name.startswith("assert_"):
        return "custom_assert"
    return "custom"


def _column_matches_reason(col_name: str, reason: str) -> bool:
    c = col_name.lower()
    if reason == "relationships":
        return c.endswith("_id") or c in {"id", "customer_id", "product_id", "store_id", "order_id"}
    if reason == "accepted_values":
        return any(k in c for k in ("status", "segment", "tier", "type", "channel"))
    if reason in {"expression", "custom_assert"}:
        return any(k in c for k in ("amount", "total", "price", "quantity", "cost", "discount", "tax"))
    return False


def _apply_dq_status(columns: List[CDMColumnInfo], model_dq: Dict[str, Any]) -> None:
    col_map: Dict[str, str] = model_dq.get("columns", {})
    reasons: Set[str] = model_dq.get("reasons", set())
    for col in columns:
        direct = col_map.get(col.name.lower())
        if direct:
            col.dq_status = direct
            continue
        inferred_warn = any(_column_matches_reason(col.name, r) for r in reasons)
        col.dq_status = "warn" if inferred_warn else "pass"


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/models", response_model=List[CDMModelDetail], summary="List all CDM models")
async def list_cdm_models(page: Dict[str, int] = Depends(pagination)) -> List[CDMModelDetail]:
    """List all dim_* and fact_* tables in the Trino CDM schema."""
    trino = TrinoClient()
    table_names = await _get_cdm_table_names(trino)

    if not table_names:
        return []

    dq_map = _load_dq_status_map(trino)

    async def _build_model(name: str) -> CDMModelDetail:
        row_count, columns = await asyncio.gather(
            _get_row_count(trino, name),
            _get_columns(trino, name),
        )
        model_dq = dq_map.get(name, {})
        if columns:
            _apply_dq_status(columns, model_dq)
        return CDMModelDetail(
            name=name,
            schema=CDM_SCHEMA,
            materialization=_materialization_for(name),
            description=f"CDM model {name}",
            row_count=row_count,
            columns=columns,
            last_updated=datetime.now(timezone.utc),
            tags=_tags_for(name),
            depends_on=[],
        )

    models = await asyncio.gather(*[_build_model(t) for t in table_names], return_exceptions=True)
    all_models = [m for m in models if isinstance(m, CDMModelDetail)]
    return all_models[page["offset"] : page["offset"] + page["limit"]]


@router.get("/models/{name}", response_model=CDMModelDetail, summary="Get CDM model details")
async def get_cdm_model(name: str) -> CDMModelDetail:
    """Return details for a single CDM model including columns, row count, and lineage."""
    trino = TrinoClient()
    om = get_om_client()

    # Check the table exists in Trino
    table_names = await _get_cdm_table_names(trino)
    if name not in table_names:
        raise HTTPException(status_code=404, detail=f"CDM model '{name}' not found.")

    # Fetch in parallel
    row_count_task = _get_row_count(trino, name)
    columns_task = _get_columns(trino, name)

    # Try to get OM metadata for the table
    fqn = f"{CDM_CATALOG}.{CDM_SCHEMA}.{name}"
    async def _get_om_meta() -> Optional[Dict[str, Any]]:
        try:
            return await om.get_table(fqn)
        except Exception:
            return None

    row_count, columns, om_meta = await asyncio.gather(
        row_count_task, columns_task, _get_om_meta()
    )
    dq_map = _load_dq_status_map(trino).get(name, {})

    last_updated = _om_table_to_last_updated(om_meta)
    description = om_meta.get("description") if om_meta else None

    # Merge OM column descriptions into our column list if available
    if om_meta:
        om_columns: List[Dict[str, Any]] = om_meta.get("columns", [])
        om_col_map = {col.get("name", "").lower(): col for col in om_columns}
        enriched: List[CDMColumnInfo] = []
        for col in columns:
            om_col = om_col_map.get(col.name.lower(), {})
            enriched.append(
                CDMColumnInfo(
                    name=col.name,
                    data_type=col.data_type,
                    nullable=col.nullable,
                    description=om_col.get("description") or col.description,
                )
            )
        columns = enriched

    if columns:
        _apply_dq_status(columns, dq_map)

    return CDMModelDetail(
        name=name,
        schema=CDM_SCHEMA,
        materialization=_materialization_for(name),
        description=description or f"CDM model {name}",
        row_count=row_count,
        columns=columns,
        last_updated=last_updated or datetime.now(timezone.utc),
        tags=_tags_for(name),
        depends_on=[],
    )


@router.get("/lineage/{table}", summary="Get lineage for a CDM table")
async def get_cdm_lineage(table: str) -> Dict[str, Any]:
    """Return upstream and downstream lineage for *table* from OpenMetadata.

    *table* can be a short name (resolved to ``CDM_CATALOG.CDM_SCHEMA.table``)
    or a fully-qualified name.
    """
    om = get_om_client()

    # Build FQN if not already qualified
    if "." not in table:
        fqn = f"{CDM_CATALOG}.{CDM_SCHEMA}.{table}"
    else:
        fqn = table

    try:
        lineage = await om.get_lineage(fqn, entity_type="table")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenMetadata lineage error: {exc}")

    # Shape the response for the frontend
    nodes: List[Dict[str, Any]] = lineage.get("nodes", [])
    edges: List[Dict[str, Any]] = lineage.get("edges", [])

    upstream = [
        n for n in nodes
        if any(
            e.get("toEntity", {}).get("id") == lineage.get("entity", {}).get("id")
            for e in edges
            if e.get("fromEntity", {}).get("id") == n.get("id")
        )
    ]
    downstream = [
        n for n in nodes
        if any(
            e.get("fromEntity", {}).get("id") == lineage.get("entity", {}).get("id")
            for e in edges
            if e.get("toEntity", {}).get("id") == n.get("id")
        )
    ]

    return {
        "table": fqn,
        "entity": lineage.get("entity", {}),
        "upstream_count": len(upstream),
        "downstream_count": len(downstream),
        "nodes": nodes,
        "edges": edges,
        "upstream": upstream,
        "downstream": downstream,
    }


@router.get("/stats", response_model=CDMStats, summary="CDM summary stats")
async def get_cdm_stats() -> CDMStats:
    """Return per-table row counts and totals for all CDM models."""
    trino = TrinoClient()
    table_names = await _get_cdm_table_names(trino)

    async def _row_count_entry(name: str) -> Dict[str, Any]:
        count = await _get_row_count(trino, name)
        return {
            "table": name,
            "fqn": f"{CDM_CATALOG}.{CDM_SCHEMA}.{name}",
            "row_count": count,
            "model_type": _classify_model(name),
        }

    entries = await asyncio.gather(*[_row_count_entry(t) for t in table_names], return_exceptions=True)
    valid_entries = [e for e in entries if isinstance(e, dict)]

    total_rows = sum(
        e["row_count"] for e in valid_entries if isinstance(e.get("row_count"), int) and e["row_count"] > 0
    )

    return CDMStats(
        total_models=len(valid_entries),
        total_rows=total_rows,
        models=valid_entries,
        last_updated=datetime.now(timezone.utc),
    )
