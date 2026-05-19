"""
wayfair_mock.py
---------------
Mock Wayfair product catalog data generator.

Roles:
  1. Standalone generator  – import generate_wayfair_products() in Airflow DAGs or tests.
  2. HTTP server           – run directly (`python wayfair_mock.py`) to serve the
                             mock API used by wayfair_mock_dag via GET /mock/wayfair/products.
  3. Trino loader          – call load_to_trino() to write generated data directly
                             into iceberg.raw.wayfair_products (useful for local testing
                             without the Airflow scheduler).

FastAPI is used so the same server also satisfies the `api` container in
docker-compose.yml.  The /mock/wayfair router is registered on the shared
FastAPI app so existing endpoints (/health, etc.) are unaffected.
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import date, datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Product catalog seed data
# ---------------------------------------------------------------------------

CATEGORIES: List[str] = [
    "Sofas",
    "Beds",
    "Desks",
    "Chairs",
    "Tables",
    "Lighting",
    "Storage",
    "Rugs",
    "Art",
    "Outdoor",
]

BRANDS: List[str] = [
    "Zipcode Design",
    "Birch Lane",
    "Mercury Row",
    "Laurel Foundry",
    "Kelly Clarkson Home",
    "Andover Mills",
    "Three Posts",
    "Mistana",
    "Wade Logan",
    "Brayden Studio",
]

# Category-specific adjectives for more realistic product names
ADJECTIVES: Dict[str, List[str]] = {
    "Sofas":    ["Sectional", "Loveseat", "Sleeper", "Futon", "Chesterfield", "Convertible"],
    "Beds":     ["Platform", "Storage", "Canopy", "Sleigh", "Daybed", "Bunk"],
    "Desks":    ["Writing", "Standing", "L-Shaped", "Corner", "Executive", "Floating"],
    "Chairs":   ["Accent", "Recliner", "Wingback", "Barrel", "Slipper", "Papasan"],
    "Tables":   ["Dining", "Coffee", "End", "Console", "Nightstand", "Pedestal"],
    "Lighting": ["Pendant", "Floor", "Table", "Chandelier", "Sconce", "Track"],
    "Storage":  ["Bookcase", "Cabinet", "Wardrobe", "Dresser", "Credenza", "Trunk"],
    "Rugs":     ["Area", "Runner", "Shag", "Persian", "Flatweave", "Outdoor"],
    "Art":      ["Canvas", "Framed", "Metal", "Abstract", "Photography", "Sculpture"],
    "Outdoor":  ["Patio", "Adirondack", "Hammock", "Garden", "Fire Pit", "Swing"],
}

COLORS: List[str] = [
    "Gray", "Navy", "Beige", "White", "Black", "Walnut", "Oak", "Ivory",
    "Teal", "Charcoal", "Sage", "Terracotta", "Blush", "Cognac",
]

# Typical price ranges (min, max) per category in USD
PRICE_RANGES: Dict[str, tuple] = {
    "Sofas":    (399.99,  3499.99),
    "Beds":     (299.99,  2999.99),
    "Desks":    (149.99,  1499.99),
    "Chairs":   (79.99,   1299.99),
    "Tables":   (99.99,   2499.99),
    "Lighting": (29.99,   599.99),
    "Storage":  (49.99,   999.99),
    "Rugs":     (39.99,   799.99),
    "Art":      (19.99,   499.99),
    "Outdoor":  (79.99,   1999.99),
}

# Typical weight ranges (lbs) per category
WEIGHT_RANGES: Dict[str, tuple] = {
    "Sofas":    (80.0,  250.0),
    "Beds":     (60.0,  200.0),
    "Desks":    (30.0,  120.0),
    "Chairs":   (15.0,   80.0),
    "Tables":   (20.0,  180.0),
    "Lighting": (2.0,    25.0),
    "Storage":  (25.0,  150.0),
    "Rugs":     (5.0,    40.0),
    "Art":      (1.0,    15.0),
    "Outdoor":  (10.0,  120.0),
}

# Typical dimension ranges (inches) per category: (W_min, W_max, D_min, D_max, H_min, H_max)
DIMENSION_RANGES: Dict[str, tuple] = {
    "Sofas":    (72, 120, 32, 45, 28, 36),
    "Beds":     (38, 80,  75, 84, 40, 60),
    "Desks":    (36, 72,  18, 30, 28, 48),
    "Chairs":   (20, 36,  20, 36, 28, 42),
    "Tables":   (18, 96,  18, 48, 16, 36),
    "Lighting": (8,  36,  8,  36, 10, 72),
    "Storage":  (24, 72,  12, 24, 30, 80),
    "Rugs":     (24, 144, 36, 120, 0,  1),
    "Art":      (12, 60,  1,   2,  8,  48),
    "Outdoor":  (24, 96,  24, 96, 12, 72),
}


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def _make_sku(category: str, index: int) -> str:
    """Generate a Wayfair-style SKU: WF-<CAT3>-<zero-padded-index>."""
    prefix = category[:3].upper()
    return f"WF-{prefix}-{index:05d}"


def _make_dimensions(category: str) -> str:
    """Generate realistic W x D x H dimension string."""
    w_min, w_max, d_min, d_max, h_min, h_max = DIMENSION_RANGES[category]
    w = random.randint(w_min, w_max)
    d = random.randint(d_min, d_max)
    h = random.randint(h_min, h_max) if h_max > h_min else h_min
    return f"{w}W x {d}D x {h}H"


def _make_product(index: int, category: str, ingestion_date: str) -> Dict:
    """
    Build a single product record that mirrors the Wayfair Open Catalog API
    response shape.
    """
    brand       = random.choice(BRANDS)
    color       = random.choice(COLORS)
    adjective   = random.choice(ADJECTIVES[category])
    price_min, price_max = PRICE_RANGES[category]
    price       = round(random.uniform(price_min, price_max), 2)
    # 0–40% markup on original price (occasionally equal = no discount)
    markup      = random.uniform(0.0, 0.4)
    original_price = round(price * (1.0 + markup), 2)
    wt_min, wt_max = WEIGHT_RANGES[category]
    weight_lbs  = round(random.uniform(wt_min, wt_max), 1)
    stock_qty   = random.randint(0, 500)
    # Items with 0 stock are still listed (back-order / notify-me)
    is_available = stock_qty > 0 or random.random() > 0.7

    return {
        "sku":            _make_sku(category, index),
        "name":           f"{brand} {color} {adjective} {category[:-1] if category.endswith('s') else category}",
        "category":       category,
        "brand":          brand,
        "color":          color,
        "price":          price,
        "original_price": original_price,
        "discount_pct":   round((1 - price / original_price) * 100, 1),
        "stock_quantity": stock_qty,
        "weight_lbs":     weight_lbs,
        "dimensions":     _make_dimensions(category),
        "rating":         round(random.uniform(3.0, 5.0), 1),
        "review_count":   random.randint(0, 5000),
        "is_available":   is_available,
        "is_free_shipping": price >= 35.0,
        "lead_time_days": random.choice([0, 1, 2, 3, 5, 7, 14, 21]),
        "ingestion_date": ingestion_date,
        "source":         "wayfair_api",
    }


def generate_wayfair_products(
    n: int = 100,
    ingestion_date: Optional[str] = None,
    seed: Optional[int] = None,
) -> List[Dict]:
    """
    Generate `n` realistic Wayfair-style product records.

    Args:
        n:               Number of products to generate.
        ingestion_date:  ISO date string (YYYY-MM-DD).  Defaults to today.
        seed:            Optional random seed for reproducible test data.

    Returns:
        List of product dicts ready for insertion into Iceberg / JSON serialisation.
    """
    if seed is not None:
        random.seed(seed)

    if ingestion_date is None:
        ingestion_date = date.today().isoformat()

    # Distribute products across categories proportionally
    products: List[Dict] = []
    for i in range(1, n + 1):
        # Cycle through categories so every run includes all types
        category = CATEGORIES[(i - 1) % len(CATEGORIES)]
        products.append(_make_product(i, category, ingestion_date))

    logger.info("Generated %d Wayfair product records for %s.", n, ingestion_date)
    return products


# ---------------------------------------------------------------------------
# Direct Trino loader (standalone / test helper)
# ---------------------------------------------------------------------------

def load_to_trino(
    products: List[Dict],
    trino_host: str = "localhost",
    trino_port: int = 8080,
    execution_date: Optional[str] = None,
) -> int:
    """
    Idempotently load a list of product dicts into iceberg.raw.wayfair_products
    via Trino.

    Returns:
        Number of rows inserted.

    Raises:
        ImportError if the `trino` package is not installed.
        RuntimeError on Trino connectivity / SQL errors.
    """
    try:
        import trino  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "The `trino` package is required: pip install trino"
        ) from exc

    if execution_date is None:
        execution_date = date.today().isoformat()

    conn = trino.dbapi.connect(
        host=trino_host,
        port=trino_port,
        user="wayfair_mock_loader",
        http_scheme="http",
    )
    cursor = conn.cursor()

    # Create table if absent
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iceberg.raw.wayfair_products (
            sku               VARCHAR,
            name              VARCHAR,
            category          VARCHAR,
            brand             VARCHAR,
            color             VARCHAR,
            price             DOUBLE,
            original_price    DOUBLE,
            discount_pct      DOUBLE,
            stock_quantity    INTEGER,
            weight_lbs        DOUBLE,
            dimensions        VARCHAR,
            rating            DOUBLE,
            review_count      INTEGER,
            is_available      BOOLEAN,
            is_free_shipping  BOOLEAN,
            lead_time_days    INTEGER,
            source            VARCHAR,
            ingestion_date    DATE,
            ingested_at       TIMESTAMP(6)
        ) WITH (
            format       = 'PARQUET',
            partitioning = ARRAY['ingestion_date']
        )
    """)

    # Idempotent: delete the partition before re-inserting
    cursor.execute(
        f"DELETE FROM iceberg.raw.wayfair_products "
        f"WHERE ingestion_date = DATE '{execution_date}'"
    )

    BATCH = 200
    inserted = 0
    for start in range(0, len(products), BATCH):
        batch = products[start : start + BATCH]
        rows = []
        for p in batch:
            def _s(v: object) -> str:
                return str(v).replace("'", "''")

            rows.append(
                f"('{_s(p['sku'])}', '{_s(p['name'])}', '{_s(p['category'])}', "
                f"'{_s(p['brand'])}', '{_s(p.get('color',''))}', "
                f"{float(p['price'])}, {float(p['original_price'])}, "
                f"{float(p.get('discount_pct', 0.0))}, {int(p['stock_quantity'])}, "
                f"{float(p['weight_lbs'])}, '{_s(p['dimensions'])}', "
                f"{float(p['rating'])}, {int(p['review_count'])}, "
                f"{'true' if p['is_available'] else 'false'}, "
                f"{'true' if p.get('is_free_shipping') else 'false'}, "
                f"{int(p.get('lead_time_days', 0))}, "
                f"'{_s(p['source'])}', "
                f"DATE '{execution_date}', current_timestamp)"
            )

        sql = (
            "INSERT INTO iceberg.raw.wayfair_products "
            "(sku, name, category, brand, color, price, original_price, "
            " discount_pct, stock_quantity, weight_lbs, dimensions, rating, "
            " review_count, is_available, is_free_shipping, lead_time_days, "
            " source, ingestion_date, ingested_at) VALUES "
            + ",\n".join(rows)
        )
        cursor.execute(sql)
        inserted += len(batch)

    conn.close()
    logger.info("Loaded %d products into iceberg.raw.wayfair_products.", inserted)
    return inserted


# ---------------------------------------------------------------------------
# FastAPI router (mounted on the shared `api` FastAPI app in api/main.py)
# ---------------------------------------------------------------------------

def get_wayfair_router():
    """
    Build and return a FastAPI APIRouter for the mock Wayfair endpoints.

    Mount in api/main.py:
        from ingestion.wayfair_mock import get_wayfair_router
        app.include_router(get_wayfair_router(), prefix="/mock/wayfair")
    """
    try:
        from fastapi import APIRouter, Query
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise ImportError(
            "FastAPI is required to serve the mock API: pip install fastapi"
        ) from exc

    router = APIRouter(tags=["mock-wayfair"])

    @router.get("/products", summary="List mock Wayfair products")
    def list_products(
        date: Optional[str] = Query(
            default=None,
            description="Ingestion date (YYYY-MM-DD). Defaults to today.",
            example="2024-06-15",
        ),
        limit: int = Query(
            default=100,
            ge=1,
            le=10000,
            description="Number of product records to return.",
        ),
        seed: Optional[int] = Query(
            default=None,
            description="Random seed for reproducible test data.",
        ),
    ) -> JSONResponse:
        """
        Return a list of mock Wayfair product records in the shape expected
        by the `extract_wayfair_data` Airflow task.
        """
        ingestion_date = date or datetime.utcnow().date().isoformat()
        products = generate_wayfair_products(
            n=limit, ingestion_date=ingestion_date, seed=seed
        )
        return JSONResponse(
            content={"products": products, "count": len(products), "date": ingestion_date}
        )

    @router.get("/products/{sku}", summary="Get a single mock product by SKU")
    def get_product(sku: str) -> JSONResponse:
        """
        Return a single mock product for a given SKU.
        SKU format: WF-<CAT3>-<00001..99999>
        """
        parts = sku.upper().split("-")
        if len(parts) != 3 or parts[0] != "WF":
            return JSONResponse(
                status_code=404,
                content={"error": f"SKU '{sku}' not found or invalid format."},
            )
        try:
            index = int(parts[2])
        except ValueError:
            return JSONResponse(
                status_code=404,
                content={"error": f"SKU '{sku}' has non-integer index."},
            )

        # Derive category from the 3-letter code
        cat3 = parts[1]
        category = next(
            (c for c in CATEGORIES if c[:3].upper() == cat3),
            CATEGORIES[0],
        )
        product = _make_product(index, category, datetime.utcnow().date().isoformat())
        product["sku"] = sku  # preserve original casing
        return JSONResponse(content=product)

    @router.get("/categories", summary="List available product categories")
    def list_categories() -> JSONResponse:
        return JSONResponse(content={"categories": CATEGORIES})

    @router.get("/brands", summary="List available brands")
    def list_brands() -> JSONResponse:
        return JSONResponse(content={"brands": BRANDS})

    return router


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Wayfair mock data generator / API server")
    subparsers = parser.add_subparsers(dest="command")

    # generate sub-command
    gen_parser = subparsers.add_parser("generate", help="Generate mock data and print JSON")
    gen_parser.add_argument("-n", "--count", type=int, default=100, help="Number of products")
    gen_parser.add_argument("-d", "--date", type=str, default=None, help="Ingestion date YYYY-MM-DD")
    gen_parser.add_argument("--seed", type=int, default=None, help="Random seed")
    gen_parser.add_argument("--preview", type=int, default=3, help="Number of rows to print")

    # load sub-command
    load_parser = subparsers.add_parser("load", help="Generate and load data into Trino/Iceberg")
    load_parser.add_argument("-n", "--count", type=int, default=100)
    load_parser.add_argument("-d", "--date", type=str, default=None)
    load_parser.add_argument("--seed", type=int, default=None)
    load_parser.add_argument("--host", type=str, default=os.getenv("TRINO_HOST", "localhost"))
    load_parser.add_argument("--port", type=int, default=int(os.getenv("TRINO_PORT", "8080")))

    # serve sub-command (starts the FastAPI dev server)
    serve_parser = subparsers.add_parser("serve", help="Start FastAPI mock server")
    serve_parser.add_argument("--host", type=str, default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true", default=False)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "generate" or args.command is None:
        count = getattr(args, "count", 100)
        ingestion_date = getattr(args, "date", None)
        seed = getattr(args, "seed", None)
        preview = getattr(args, "preview", 3)
        products = generate_wayfair_products(n=count, ingestion_date=ingestion_date, seed=seed)
        print(json.dumps(products[:preview], indent=2))
        print(f"\n... ({len(products)} total products generated)")

    elif args.command == "load":
        products = generate_wayfair_products(n=args.count, ingestion_date=args.date, seed=args.seed)
        rows = load_to_trino(
            products,
            trino_host=args.host,
            trino_port=args.port,
            execution_date=args.date,
        )
        print(f"Loaded {rows} rows into iceberg.raw.wayfair_products.")

    elif args.command == "serve":
        try:
            from fastapi import FastAPI
            import uvicorn
        except ImportError:
            print("ERROR: fastapi and uvicorn are required for the serve command.")
            print("  pip install fastapi uvicorn")
            raise SystemExit(1)

        app = FastAPI(title="Retail AI Data Hub – Mock API", version="0.1.0")
        app.include_router(get_wayfair_router(), prefix="/mock/wayfair")

        @app.get("/health")
        def health():
            return {"status": "ok"}

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
