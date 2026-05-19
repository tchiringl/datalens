"""
wayfair_mock_dag.py
-------------------
Simulates daily ingestion from an external Wayfair-style REST API.

Pipeline stages:
  extract  → Pulls mock product/inventory records from the local FastAPI mock server.
  validate → Schema and business-rule validation; logs warnings but does NOT block load.
  load     → Idempotent upsert into Iceberg `raw.wayfair_products` via Trino.

Runs daily; catchup=True so historical dates are backfilled on first deploy.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import requests
import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TRINO_HOST = os.getenv("TRINO_HOST", "trino")
TRINO_PORT = int(os.getenv("TRINO_PORT", "8080"))
MOCK_API_BASE = os.getenv("MOCK_API_URL", "http://api:8000/mock/wayfair")

# Maximum number of rows we attempt to insert in one Airflow task run.
# The mock server caps its own response; this is a safeguard.
MAX_PRODUCTS = int(os.getenv("WAYFAIR_MAX_PRODUCTS", "1000"))

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
default_args = {
    "owner": "datahub",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

# ---------------------------------------------------------------------------
# Required fields and validation rules
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: List[str] = ["sku", "name", "price", "category", "stock_quantity"]


# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------

def extract_wayfair_data(**context) -> None:
    """
    Pull mock product data from the Wayfair-style REST API for a given
    execution date.  Pushes the list of product dicts to XCom under the
    key 'wayfair_products'.

    The mock API is served by the `api` FastAPI container defined in
    docker-compose.yml and mirrors the shape of the real Wayfair Open
    Catalog API.
    """
    execution_date: str = context["ds"]          # YYYY-MM-DD string
    logger.info("Extracting Wayfair data for date: %s", execution_date)

    url = f"{MOCK_API_BASE}/products"
    params = {"date": execution_date, "limit": MAX_PRODUCTS}

    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Cannot reach mock Wayfair API at {url}. "
            "Is the `api` container running? Error: " + str(exc)
        ) from exc

    payload = resp.json()

    # The mock API wraps the list inside a `products` key
    if isinstance(payload, list):
        products: List[Dict] = payload
    elif isinstance(payload, dict) and "products" in payload:
        products = payload["products"]
    else:
        raise ValueError(
            f"Unexpected API response shape. Expected list or {{products: [...]}}. "
            f"Got keys: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}"
        )

    logger.info("Extracted %d products from Wayfair API for %s.", len(products), execution_date)
    context["task_instance"].xcom_push(key="wayfair_products", value=products)
    context["task_instance"].xcom_push(key="product_count", value=len(products))


def validate_wayfair_data(**context) -> None:
    """
    Validate extracted product records against:
      - Required field presence (no None / missing key)
      - Non-negative price
      - Non-negative stock quantity
      - SKU format (non-empty string)

    Validation errors are logged and pushed to XCom as a list.  The load
    task is always attempted even if warnings exist, but the task sets a
    warning log entry so operators can inspect issues.
    """
    ti = context["task_instance"]
    products: List[Dict] = ti.xcom_pull(task_ids="extract_wayfair_data", key="wayfair_products")

    if not products:
        logger.warning("No products to validate. Skipping validation.")
        ti.xcom_push(key="validation_errors", value=[])
        ti.xcom_push(key="valid_count", value=0)
        return

    errors: List[str] = []
    valid_count = 0

    for i, product in enumerate(products):
        row_errors: List[str] = []

        # Required-field check
        for field in REQUIRED_FIELDS:
            if field not in product or product[field] is None:
                row_errors.append(f"missing required field '{field}'")

        # Business-rule checks (only when fields are present)
        if "price" in product and product["price"] is not None:
            try:
                if float(product["price"]) < 0:
                    row_errors.append(f"negative price ({product['price']})")
            except (TypeError, ValueError):
                row_errors.append(f"non-numeric price ({product['price']!r})")

        if "stock_quantity" in product and product["stock_quantity"] is not None:
            try:
                if int(product["stock_quantity"]) < 0:
                    row_errors.append(f"negative stock_quantity ({product['stock_quantity']})")
            except (TypeError, ValueError):
                row_errors.append(f"non-integer stock_quantity ({product['stock_quantity']!r})")

        if "sku" in product:
            sku = product["sku"]
            if not isinstance(sku, str) or not sku.strip():
                row_errors.append("empty or non-string SKU")

        if row_errors:
            sku_label = product.get("sku", f"row_{i}")
            for err in row_errors:
                errors.append(f"[{sku_label}] {err}")
        else:
            valid_count += 1

    if errors:
        # Emit the first 20 errors to avoid flooding logs; full list goes to XCom
        logger.warning(
            "Validation completed with %d error(s) across %d records. "
            "First errors: %s",
            len(errors),
            len(products),
            errors[:20],
        )
    else:
        logger.info("Validation passed: all %d products are valid.", len(products))

    ti.xcom_push(key="validation_errors", value=errors)
    ti.xcom_push(key="valid_count", value=valid_count)


def load_to_iceberg(**context) -> None:
    """
    Idempotently load validated Wayfair products into the Iceberg raw layer.

    Strategy:
      1. CREATE TABLE IF NOT EXISTS iceberg.raw.wayfair_products
      2. DELETE existing rows for `ingestion_date` (partition prune → fast)
      3. Batch-INSERT all rows for that date

    Requires the `trino` Python package and a running Trino coordinator that
    has the `iceberg` catalog configured (see infra/trino/catalog/iceberg.properties).
    """
    import trino  # type: ignore

    ti = context["task_instance"]
    products: List[Dict] = ti.xcom_pull(task_ids="extract_wayfair_data", key="wayfair_products")
    execution_date: str = context["ds"]

    if not products:
        logger.warning("No products to load for %s. Exiting load task.", execution_date)
        return

    logger.info(
        "Connecting to Trino at %s:%d to load %d products for %s.",
        TRINO_HOST,
        TRINO_PORT,
        len(products),
        execution_date,
    )

    conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user="airflow",
        http_scheme="http",
    )
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # 1. Ensure the table exists
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iceberg.raw.wayfair_products (
            sku               VARCHAR,
            name              VARCHAR,
            category          VARCHAR,
            brand             VARCHAR,
            price             DOUBLE,
            original_price    DOUBLE,
            stock_quantity    INTEGER,
            weight_lbs        DOUBLE,
            dimensions        VARCHAR,
            rating            DOUBLE,
            review_count      INTEGER,
            is_available      BOOLEAN,
            source            VARCHAR,
            ingestion_date    DATE,
            ingested_at       TIMESTAMP(6)
        ) WITH (
            format       = 'PARQUET',
            partitioning = ARRAY['ingestion_date']
        )
    """)
    logger.info("Ensured table iceberg.raw.wayfair_products exists.")

    # ------------------------------------------------------------------
    # 2. Delete existing rows for this partition (idempotent re-run)
    # ------------------------------------------------------------------
    cursor.execute(
        f"DELETE FROM iceberg.raw.wayfair_products "
        f"WHERE ingestion_date = DATE '{execution_date}'"
    )
    logger.info("Deleted existing rows for ingestion_date=%s.", execution_date)

    # ------------------------------------------------------------------
    # 3. Batch-insert – use a single multi-row VALUES statement for
    #    efficiency instead of one round-trip per product.
    # ------------------------------------------------------------------
    BATCH_SIZE = 200
    total_inserted = 0

    for batch_start in range(0, len(products), BATCH_SIZE):
        batch = products[batch_start : batch_start + BATCH_SIZE]
        value_rows = []

        for p in batch:
            sku           = str(p.get("sku", "")).replace("'", "''")
            name          = str(p.get("name", "")).replace("'", "''")
            category      = str(p.get("category", "")).replace("'", "''")
            brand         = str(p.get("brand", "")).replace("'", "''")
            price         = float(p.get("price", 0.0))
            original_price = float(p.get("original_price", price))
            stock_qty     = int(p.get("stock_quantity", 0))
            weight_lbs    = float(p.get("weight_lbs", 0.0))
            dimensions    = str(p.get("dimensions", "")).replace("'", "''")
            rating        = float(p.get("rating", 0.0))
            review_count  = int(p.get("review_count", 0))
            is_available  = "true" if p.get("is_available", True) else "false"
            source        = str(p.get("source", "wayfair_api")).replace("'", "''")

            value_rows.append(
                f"('{sku}', '{name}', '{category}', '{brand}', "
                f"{price}, {original_price}, {stock_qty}, {weight_lbs}, "
                f"'{dimensions}', {rating}, {review_count}, {is_available}, "
                f"'{source}', DATE '{execution_date}', current_timestamp)"
            )

        insert_sql = (
            "INSERT INTO iceberg.raw.wayfair_products "
            "(sku, name, category, brand, price, original_price, stock_quantity, "
            " weight_lbs, dimensions, rating, review_count, is_available, source, "
            " ingestion_date, ingested_at) VALUES "
            + ",\n".join(value_rows)
        )
        cursor.execute(insert_sql)
        total_inserted += len(batch)
        logger.info(
            "Inserted batch %d–%d (%d rows so far).",
            batch_start + 1,
            batch_start + len(batch),
            total_inserted,
        )

    conn.close()
    logger.info(
        "Load complete: %d Wayfair products loaded to iceberg.raw.wayfair_products "
        "for ingestion_date=%s.",
        total_inserted,
        execution_date,
    )
    context["task_instance"].xcom_push(key="rows_loaded", value=total_inserted)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="wayfair_mock_ingestion",
    default_args=default_args,
    description="Daily ingestion of Wayfair mock API data into Iceberg raw layer",
    schedule_interval="@daily",
    start_date=days_ago(7),
    catchup=True,
    tags=["datahub", "ingestion", "wayfair", "iceberg"],
    max_active_runs=1,
    doc_md="""
## Wayfair Mock Ingestion DAG

Pulls furniture/home-decor product records from the local FastAPI mock server
(which simulates the Wayfair Open Catalog API) and lands them in the Iceberg
raw layer for downstream dbt transformation.

**Idempotent:** Re-running for any date is safe — existing rows are deleted
before re-insert.

**Schema** (`iceberg.raw.wayfair_products`):
| column         | type        |
|----------------|-------------|
| sku            | VARCHAR     |
| name           | VARCHAR     |
| category       | VARCHAR     |
| brand          | VARCHAR     |
| price          | DOUBLE      |
| original_price | DOUBLE      |
| stock_quantity | INTEGER     |
| weight_lbs     | DOUBLE      |
| dimensions     | VARCHAR     |
| rating         | DOUBLE      |
| review_count   | INTEGER     |
| is_available   | BOOLEAN     |
| source         | VARCHAR     |
| ingestion_date | DATE (part) |
| ingested_at    | TIMESTAMP   |
""",
) as dag:

    extract = PythonOperator(
        task_id="extract_wayfair_data",
        python_callable=extract_wayfair_data,
        doc_md="Call mock Wayfair REST API and push product list to XCom.",
    )

    validate = PythonOperator(
        task_id="validate_wayfair_data",
        python_callable=validate_wayfair_data,
        doc_md="Validate required fields and business rules; log warnings on failure.",
    )

    load = PythonOperator(
        task_id="load_to_iceberg",
        python_callable=load_to_iceberg,
        doc_md="Idempotently load products into iceberg.raw.wayfair_products via Trino.",
    )

    extract >> validate >> load
