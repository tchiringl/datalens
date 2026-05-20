import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from services.om_client import OpenMetadataClient

REPORTS_DIR = Path("/app/profiling/reports")
MANIFEST_PATH = Path("/app/profiling/reports/manifest.json")
DEFAULT_POC_TABLES: List[Tuple[str, str, str]] = [
    ("postgres", "public", "customers"),
    ("postgres", "public", "orders"),
    ("postgres", "public", "products"),
]


def _parse_trino_coordinates(table_fqn: str) -> Optional[Tuple[str, str, str]]:
    parts = table_fqn.split(".")
    if len(parts) < 3:
        return None
    return parts[-3], parts[-2], parts[-1]


def _read_manifest() -> List[Dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_manifest(rows: List[Dict[str, Any]]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _run_query(catalog: str, schema: str, table: str, limit: int) -> pd.DataFrame:
    import trino  # type: ignore

    host = "trino"
    port = 8080
    user = "profiler"
    conn = trino.dbapi.connect(host=host, port=port, user=user, http_scheme="http")
    query = f'SELECT * FROM "{catalog}"."{schema}"."{table}" LIMIT {max(1, limit)}'
    try:
        return pd.read_sql(query, conn)
    finally:
        conn.close()


def _build_profile(df: pd.DataFrame, title: str, output_path: Path) -> None:
    from ydata_profiling import ProfileReport  # type: ignore

    profile = ProfileReport(
        df,
        title=title,
        minimal=True,
        explorative=False,
    )
    profile.to_file(str(output_path))


async def generate_assessment_report(
    source_id: str,
    table_limit: int = 3,
    row_limit: int = 20000,
) -> Dict[str, Any]:
    om = OpenMetadataClient()
    tables = await om.list_tables(service_name=source_id, limit=max(1, table_limit))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc)
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ")

    report_rows: List[Dict[str, Any]] = []
    targets: List[Tuple[str, str, str]] = []
    if source_id == "__default__":
        targets = DEFAULT_POC_TABLES[:table_limit]
    else:
        for table in tables[:table_limit]:
            fqn = table.get("fullyQualifiedName", "")
            coords = _parse_trino_coordinates(fqn)
            if not coords:
                continue
            targets.append(coords)

    if not targets:
        raise ValueError(
            f"No tables found for source '{source_id}'. "
            "Use source '__default__' for built-in POC tables."
        )

    for catalog, schema, table_name in targets:
        df = _run_query(catalog, schema, table_name, row_limit)
        if df.empty:
            continue

        file_name = f"{source_id}_{catalog}_{schema}_{table_name}_{run_id}.html"
        output_path = REPORTS_DIR / file_name
        title = f"Data Assessment: {catalog}.{schema}.{table_name}"
        _build_profile(df, title, output_path)

        report_rows.append(
            {
                "source_id": source_id,
                "table_fqn": f"{catalog}.{schema}.{table_name}",
                "file_name": file_name,
                "report_url": f"/assessment-reports/{file_name}",
                "row_count_profiled": int(len(df)),
                "column_count": int(len(df.columns)),
                "created_at": created_at.isoformat(),
            }
        )

    if not report_rows:
        raise ValueError("No report generated. Ensure tables are queryable and non-empty.")

    existing = _read_manifest()
    manifest = report_rows + existing
    _write_manifest(manifest[:200])
    return {
        "source_id": source_id,
        "created_at": created_at.isoformat(),
        "reports": report_rows,
    }


def list_assessment_reports(source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = _read_manifest()
    if source_id:
        rows = [r for r in rows if r.get("source_id") == source_id]
    return rows
