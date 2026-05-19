"""
run_profile.py
--------------
YData Profiling script for the Retail AI Data Lens CDM and raw source tables.

What it does:
  - Connects to Trino to read CDM and source tables
  - Generates a rich HTML profiling report for each table (column stats,
    distributions, correlations, missing-value heatmaps, sample data)
  - Saves reports to ./profiling/reports/<catalog>_<schema>_<table>_<ts>.html
  - Prints a final summary of generated / failed reports

Usage:
  # All tables (default):
  python profiling/run_profile.py

  # Specific tables only:
  python profiling/run_profile.py --tables iceberg.cdm.fact_orders iceberg.cdm.dim_customers

  # Override Trino connection:
  TRINO_HOST=my-trino TRINO_PORT=8080 python profiling/run_profile.py

  # Limit rows per table (faster for large tables):
  python profiling/run_profile.py --limit 10000

Requirements:
  pip install ydata-profiling pandas trino sqlalchemy
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TRINO_HOST = os.getenv("TRINO_HOST", "localhost")
TRINO_PORT = int(os.getenv("TRINO_PORT", "8080"))
TRINO_USER = os.getenv("TRINO_USER", "profiler")
OUTPUT_DIR = Path(os.getenv("PROFILING_OUTPUT_DIR", "./profiling/reports"))

# Default tables to profile: (catalog, schema, table, date_filter_column or None)
# date_filter_column is used to limit the scan to data from 2024-01-01 onward
# (avoids pulling years of history during the POC).
DEFAULT_TABLES: List[Tuple[str, str, str, Optional[str]]] = [
    ("iceberg",  "cdm",    "fact_orders",     "order_date"),
    ("iceberg",  "cdm",    "dim_customers",   None),
    ("iceberg",  "cdm",    "dim_products",    None),
    ("iceberg",  "raw",    "wayfair_products","ingestion_date"),
    ("postgres", "public", "customers",       None),
    ("postgres", "public", "orders",          "order_date"),
    ("postgres", "public", "products",        None),
]

# Default row limit per table (0 = no limit)
DEFAULT_ROW_LIMIT = int(os.getenv("PROFILING_ROW_LIMIT", "50000"))

# Minimum date for date-filtered tables
DATE_FILTER_FROM = os.getenv("PROFILING_DATE_FROM", "2024-01-01")

# YData profiling configuration overrides
YDATA_CONFIG = {
    "title_prefix": "Data Lens Profile: ",
    "explorative": True,
    "correlations": {
        "pearson":  {"calculate": True},
        "spearman": {"calculate": False},
        "kendall":  {"calculate": False},
        "phi_k":    {"calculate": False},
        "cramers":  {"calculate": False},
    },
    "missing_diagrams": {
        "bar":     True,
        "matrix":  True,
        "heatmap": True,
    },
    "samples": {
        "head": 10,
        "tail": 10,
    },
    "interactions": {
        "continuous": False,   # disable for performance on wide tables
    },
    "plot": {
        "histogram": {"bayesian_blocks_bins": False},
    },
}


# ---------------------------------------------------------------------------
# Trino connection helpers
# ---------------------------------------------------------------------------

def get_trino_connection():
    """Return a raw trino.dbapi connection."""
    try:
        import trino  # type: ignore
    except ImportError as exc:
        raise ImportError("Install the trino package: pip install trino") from exc

    return trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        http_scheme="http",
    )


def read_table_to_df(
    catalog: str,
    schema: str,
    table: str,
    date_col: Optional[str] = None,
    limit: int = DEFAULT_ROW_LIMIT,
) -> pd.DataFrame:
    """
    Execute a SELECT against Trino and return a DataFrame.

    Args:
        catalog:   Trino catalog name (e.g. 'iceberg', 'postgres').
        schema:    Schema name within the catalog.
        table:     Table name.
        date_col:  Optional column to filter by DATE_FILTER_FROM.
        limit:     Max rows to fetch. 0 = no limit.

    Returns:
        pandas DataFrame with the query result.

    Raises:
        RuntimeError on connectivity or SQL errors.
    """
    fqn = f"{catalog}.{schema}.{table}"
    where_clause = ""
    if date_col:
        where_clause = f" WHERE {date_col} >= DATE '{DATE_FILTER_FROM}'"

    limit_clause = f" LIMIT {limit}" if limit > 0 else ""
    query = f"SELECT * FROM {fqn}{where_clause}{limit_clause}"

    logger.info("Fetching %s (limit=%d, filter=%s) ...", fqn, limit, date_col or "none")
    logger.debug("Query: %s", query)

    try:
        conn = get_trino_connection()
        df = pd.read_sql(query, conn)
        conn.close()
    except Exception as exc:
        raise RuntimeError(f"Failed to read {fqn}: {exc}") from exc

    logger.info("  → %d rows × %d columns", len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------

def profile_table(
    catalog: str,
    schema: str,
    table: str,
    date_col: Optional[str] = None,
    limit: int = DEFAULT_ROW_LIMIT,
    output_dir: Path = OUTPUT_DIR,
) -> str:
    """
    Profile a single table and write an HTML report.

    Args:
        catalog, schema, table:  Table coordinates.
        date_col:  Optional column to filter rows by DATE_FILTER_FROM.
        limit:     Max rows to pull from Trino.
        output_dir: Directory where the HTML report is saved.

    Returns:
        Absolute path to the generated HTML report.

    Raises:
        RuntimeError if data fetch or profiling fails.
    """
    try:
        from ydata_profiling import ProfileReport  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Install ydata-profiling: pip install ydata-profiling"
        ) from exc

    fqn = f"{catalog}.{schema}.{table}"
    df = read_table_to_df(catalog, schema, table, date_col=date_col, limit=limit)

    if df.empty:
        logger.warning("Table %s returned 0 rows — skipping profiling.", fqn)
        raise RuntimeError(f"{fqn} returned an empty DataFrame.")

    title = f"{YDATA_CONFIG['title_prefix']}{fqn}"
    logger.info("Building profiling report for %s (%d rows)...", fqn, len(df))

    profile = ProfileReport(
        df,
        title=title,
        explorative=YDATA_CONFIG["explorative"],
        correlations=YDATA_CONFIG["correlations"],
        missing_diagrams=YDATA_CONFIG["missing_diagrams"],
        samples=YDATA_CONFIG["samples"],
        interactions=YDATA_CONFIG["interactions"],
        plot=YDATA_CONFIG["plot"],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{catalog}_{schema}_{table}_{timestamp}.html"
    output_path = output_dir / filename

    profile.to_file(str(output_path))
    logger.info("Report saved: %s", output_path)
    return str(output_path.resolve())


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_profiling(
    tables: Optional[List[Tuple[str, str, str, Optional[str]]]] = None,
    limit: int = DEFAULT_ROW_LIMIT,
    output_dir: Path = OUTPUT_DIR,
    fail_fast: bool = False,
) -> Tuple[List[str], List[str]]:
    """
    Profile all specified tables and return (succeeded, failed) path lists.

    Args:
        tables:    List of (catalog, schema, table, date_col) tuples.
                   Defaults to DEFAULT_TABLES.
        limit:     Row limit per table.
        output_dir: Report output directory.
        fail_fast: Raise immediately on the first error instead of continuing.

    Returns:
        (succeeded_paths, failed_labels)
    """
    if tables is None:
        tables = DEFAULT_TABLES

    succeeded: List[str] = []
    failed: List[str] = []

    total = len(tables)
    for i, entry in enumerate(tables, start=1):
        catalog, schema, table, date_col = entry
        fqn = f"{catalog}.{schema}.{table}"
        logger.info("[%d/%d] Profiling %s...", i, total, fqn)
        try:
            path = profile_table(
                catalog=catalog,
                schema=schema,
                table=table,
                date_col=date_col,
                limit=limit,
                output_dir=output_dir,
            )
            succeeded.append(path)
        except Exception as exc:
            logger.error("FAILED to profile %s: %s", fqn, exc)
            failed.append(fqn)
            if fail_fast:
                raise

    return succeeded, failed


def _parse_table_arg(raw: str) -> Tuple[str, str, str, Optional[str]]:
    """
    Parse a table argument in the form catalog.schema.table[:date_col].

    Examples:
      iceberg.cdm.fact_orders:order_date
      postgres.public.customers
    """
    if ":" in raw:
        fqn_part, date_col = raw.split(":", 1)
    else:
        fqn_part, date_col = raw, None

    parts = fqn_part.strip().split(".")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Table must be in the form catalog.schema.table[:date_col]. Got: '{raw}'"
        )
    return parts[0], parts[1], parts[2], date_col


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Generate YData Profiling HTML reports for Trino-accessible tables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Profile all default tables:
  python profiling/run_profile.py

  # Profile specific tables (use :col for date filtering):
  python profiling/run_profile.py --tables iceberg.cdm.fact_orders:order_date postgres.public.customers

  # Limit to 10,000 rows per table:
  python profiling/run_profile.py --limit 10000

  # Save reports to a custom directory:
  python profiling/run_profile.py --output /tmp/reports

  # Fail immediately on first error:
  python profiling/run_profile.py --fail-fast
        """,
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        type=_parse_table_arg,
        default=None,
        metavar="catalog.schema.table[:date_col]",
        help=(
            "One or more fully-qualified table names to profile. "
            "Append :column_name to apply a date filter (>= 2024-01-01). "
            "Defaults to the built-in DEFAULT_TABLES list."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_ROW_LIMIT,
        metavar="N",
        help=f"Max rows to fetch per table (default: {DEFAULT_ROW_LIMIT}; 0 = unlimited).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory for HTML reports (default: {OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--date-from",
        type=str,
        default=DATE_FILTER_FROM,
        metavar="YYYY-MM-DD",
        help=f"Minimum date for date-filtered tables (default: {DATE_FILTER_FROM}).",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=False,
        help="Stop immediately on the first profiling error.",
    )

    args = parser.parse_args()

    # Apply CLI overrides to module-level config
    DATE_FILTER_FROM = args.date_from  # noqa: F841

    succeeded, failed = run_profiling(
        tables=args.tables,
        limit=args.limit,
        output_dir=args.output,
        fail_fast=args.fail_fast,
    )

    print("\n" + "=" * 65)
    print("  PROFILING SUMMARY")
    print("=" * 65)
    print(f"  Succeeded : {len(succeeded)}")
    for path in succeeded:
        print(f"    {path}")
    print(f"  Failed    : {len(failed)}")
    for label in failed:
        print(f"    {label}")
    print("=" * 65)

    sys.exit(1 if failed else 0)
