"""
Mock data router — returns deterministic fake data for demo / frontend development.

Endpoints
---------
GET /mock/wayfair/products   100 mock Wayfair-style product records
GET /mock/stats              platform KPI dashboard stats
GET /mock/activity           recent activity feed (last 10 events)
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter()

# ---------------------------------------------------------------------------
# Deterministic seed so responses are stable across calls
# ---------------------------------------------------------------------------
_RNG = random.Random(42)

# ---------------------------------------------------------------------------
# Data tables used for generation
# ---------------------------------------------------------------------------

_CATEGORIES = [
    "Furniture", "Rugs", "Lighting", "Bedding", "Kitchen",
    "Bath", "Outdoor", "Storage", "Decor", "Mirrors",
]

_BRANDS = [
    "Wayfair Basics", "Andover Mills", "Birch Lane", "Mercury Row",
    "Three Posts", "Corrigan Studio", "Wade Logan", "Kelly Clover",
    "August Grove", "Breakwater Bay",
]

_COLORS = ["Brown", "White", "Gray", "Black", "Blue", "Beige", "Natural", "Navy", "Gold", "Green"]

_STATUSES = ["active", "active", "active", "discontinued", "out_of_stock"]

_ADJECTIVES = [
    "Modern", "Rustic", "Industrial", "Farmhouse", "Contemporary",
    "Classic", "Elegant", "Minimalist", "Bohemian", "Coastal",
]

_NOUNS = [
    "Sofa", "Chair", "Table", "Lamp", "Rug", "Mirror", "Shelf",
    "Bed Frame", "Dresser", "Cabinet", "Ottoman", "Bench",
]


def generate_wayfair_products(n: int = 100) -> List[Dict[str, Any]]:
    """Return *n* deterministic fake Wayfair-style product records."""
    rng = random.Random(42)
    products = []
    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    for i in range(1, n + 1):
        sku = f"WF-{rng.randint(100000, 999999)}"
        category = rng.choice(_CATEGORIES)
        brand = rng.choice(_BRANDS)
        color = rng.choice(_COLORS)
        adj = rng.choice(_ADJECTIVES)
        noun = rng.choice(_NOUNS)
        name = f"{adj} {color} {noun}"

        price = round(rng.uniform(29.99, 1499.99), 2)
        sale = rng.random() < 0.3
        sale_price = round(price * rng.uniform(0.6, 0.85), 2) if sale else None

        rating = round(rng.uniform(3.0, 5.0), 1)
        review_count = rng.randint(0, 4200)

        days_offset = rng.randint(0, 500)
        listed_at = base_date + timedelta(days=days_offset)

        products.append(
            {
                "product_id": str(uuid.UUID(int=rng.getrandbits(128))),
                "sku": sku,
                "name": name,
                "category": category,
                "brand": brand,
                "color": color,
                "price": price,
                "sale_price": sale_price,
                "on_sale": sale,
                "rating": rating,
                "review_count": review_count,
                "in_stock": rng.random() > 0.1,
                "status": rng.choice(_STATUSES),
                "listed_at": listed_at.isoformat(),
                "weight_lbs": round(rng.uniform(1.0, 85.0), 1),
                "dimensions": {
                    "width_in": round(rng.uniform(10, 96), 1),
                    "depth_in": round(rng.uniform(10, 48), 1),
                    "height_in": round(rng.uniform(8, 84), 1),
                },
                "tags": rng.sample(
                    ["sale", "new", "bestseller", "clearance", "exclusive", "trending"],
                    k=rng.randint(0, 3),
                ),
            }
        )
    return products


# ---------------------------------------------------------------------------
# Activity event helpers
# ---------------------------------------------------------------------------

_ACTIVITY_TEMPLATES = [
    ("pipeline_success", "Pipeline {subject} completed successfully", "success"),
    ("pipeline_failure", "Pipeline {subject} failed — check logs", "error"),
    ("source_synced", "Source '{subject}' metadata synced", "info"),
    ("dq_alert", "DQ test failed on table {subject}", "warning"),
    ("model_updated", "CDM model {subject} refreshed ({rows} rows)", "info"),
    ("source_added", "New source '{subject}' registered", "success"),
]

_PIPELINE_NAMES = [
    "ingest_wayfair_products", "ingest_retail_orders", "dbt_transform",
    "om_metadata_sync", "profiling_run",
]

_TABLE_NAMES = [
    "fact_orders", "dim_customers", "dim_products", "fact_inventory",
    "stg_wayfair_products",
]

_SOURCE_NAMES = ["retail_postgres", "wayfair_api", "iceberg_warehouse"]


def _generate_activity_feed(n: int = 10) -> List[Dict[str, Any]]:
    rng = random.Random(99)
    now = datetime.now(timezone.utc)
    events = []

    for i in range(n):
        template_key, template_msg, level = rng.choice(_ACTIVITY_TEMPLATES)

        if "pipeline" in template_key:
            subject = rng.choice(_PIPELINE_NAMES)
        elif "model" in template_key:
            subject = rng.choice(_TABLE_NAMES)
        elif "source" in template_key:
            subject = rng.choice(_SOURCE_NAMES)
        else:
            subject = rng.choice(_TABLE_NAMES)

        minutes_ago = rng.randint(1, 480)
        ts = now - timedelta(minutes=minutes_ago)

        message = template_msg.format(
            subject=subject,
            rows=f"{rng.randint(1000, 50000):,}",
        )

        events.append(
            {
                "id": str(uuid.UUID(int=rng.getrandbits(128))),
                "type": template_key,
                "level": level,
                "message": message,
                "subject": subject,
                "timestamp": ts.isoformat(),
            }
        )

    # Sort newest first
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/wayfair/products", summary="Mock Wayfair product catalogue (100 records)")
async def mock_wayfair_products() -> List[Dict[str, Any]]:
    """Return 100 deterministic mock Wayfair-style product records.

    Used by the ingestion simulation and frontend demo mode.
    """
    return generate_wayfair_products(100)


@router.get("/stats", summary="Mock platform KPI stats")
async def mock_stats() -> Dict[str, Any]:
    """Return realistic-looking platform KPI numbers for the dashboard."""
    return {
        "total_sources": 4,
        "cdm_models": 7,
        "dq_tests_passing": 33,
        "dq_tests_total": 36,
        "dq_coverage_pct": round(33 / 36 * 100, 1),
        "pipeline_runs_today": 5,
        "total_records_processed": 22847,
        "last_pipeline_run": "2024-04-16T14:22:00Z",
        "sources": [
            {"name": "retail_postgres", "status": "connected", "tables": 12},
            {"name": "wayfair_api", "status": "connected", "tables": 3},
            {"name": "iceberg_warehouse", "status": "connected", "tables": 8},
            {"name": "redshift_analytics", "status": "syncing", "tables": 0},
        ],
        "recent_pipeline_statuses": {
            "success": 3,
            "running": 1,
            "failed": 1,
            "queued": 0,
        },
    }


@router.get("/activity", summary="Mock recent activity feed")
async def mock_activity() -> List[Dict[str, Any]]:
    """Return the last 10 mock activity events for the dashboard feed."""
    return _generate_activity_feed(10)
