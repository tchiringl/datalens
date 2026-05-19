"""
Health check endpoints.

GET /health          — overall platform status (healthy / degraded / unhealthy)
GET /health/detailed — per-service breakdown with latency measurements
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi import APIRouter

router = APIRouter()

# ---------------------------------------------------------------------------
# Service coordinates (resolved from env or defaults for Docker Compose)
# ---------------------------------------------------------------------------
TRINO_HOST = os.getenv("TRINO_HOST", "trino")
TRINO_PORT = os.getenv("TRINO_PORT", "8080")
AIRFLOW_HOST = os.getenv("AIRFLOW_HOST", "airflow-webserver")
AIRFLOW_PORT = "8082"
OM_HOST = os.getenv("OM_HOST", "openmetadata-server")
OM_PORT = os.getenv("OM_PORT", "8585")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

_PROBE_TIMEOUT = 8.0  # seconds per service probe


# ---------------------------------------------------------------------------
# Individual service probes
# ---------------------------------------------------------------------------


async def _probe_trino() -> Dict[str, Any]:
    """Hit Trino's /v1/info endpoint."""
    url = f"http://{TRINO_HOST}:{TRINO_PORT}/v1/info"
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(url)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            if resp.status_code == 200:
                info = resp.json()
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "version": info.get("nodeVersion", {}).get("version", "unknown"),
                }
            return {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "error": f"HTTP {resp.status_code}",
            }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": str(exc),
        }


async def _probe_airflow() -> Dict[str, Any]:
    """Hit Airflow's /health endpoint (webserver + scheduler / metadatabase)."""
    url = f"http://{AIRFLOW_HOST}:{AIRFLOW_PORT}/health"
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(url)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            if resp.status_code == 200:
                data = resp.json()
                scheduler_ok = (
                    data.get("scheduler", {}).get("status", "").lower() == "healthy"
                )
                metadb_ok = (
                    data.get("metadatabase", {}).get("status", "").lower() == "healthy"
                )
                overall = "healthy" if (scheduler_ok and metadb_ok) else "degraded"
                return {
                    "status": overall,
                    "latency_ms": latency_ms,
                    "scheduler": data.get("scheduler", {}),
                    "metadatabase": data.get("metadatabase", {}),
                }
            return {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "error": f"HTTP {resp.status_code}",
            }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": str(exc),
        }


async def _probe_openmetadata() -> Dict[str, Any]:
    """Hit OpenMetadata's /api/v1/system/status endpoint."""
    url = f"http://{OM_HOST}:{OM_PORT}/api/v1/system/status"
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.get(url)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            if resp.status_code == 200:
                return {"status": "healthy", "latency_ms": latency_ms}
            return {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "error": f"HTTP {resp.status_code}",
            }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": str(exc),
        }


async def _probe_postgres() -> Dict[str, Any]:
    """TCP-level probe: try to open a socket to Postgres."""
    t0 = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(POSTGRES_HOST, int(POSTGRES_PORT)),
            timeout=_PROBE_TIMEOUT,
        )
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        return {
            "status": "unhealthy",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Aggregate helper
# ---------------------------------------------------------------------------


def _overall_status(services: Dict[str, Dict[str, Any]]) -> str:
    statuses = [svc.get("status", "unhealthy") for svc in services.values()]
    if all(s == "healthy" for s in statuses):
        return "healthy"
    if all(s == "unhealthy" for s in statuses):
        return "unhealthy"
    return "degraded"


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/health", summary="Overall platform health")
async def health_summary() -> Dict[str, Any]:
    """Return a single status string indicating overall platform health.

    Runs all service probes concurrently and aggregates the results.
    """
    trino_result, airflow_result, om_result, pg_result = await asyncio.gather(
        _probe_trino(),
        _probe_airflow(),
        _probe_openmetadata(),
        _probe_postgres(),
        return_exceptions=False,
    )

    services = {
        "trino": trino_result,
        "airflow": airflow_result,
        "openmetadata": om_result,
        "postgres": pg_result,
    }

    return {
        "status": _overall_status(services),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {name: svc["status"] for name, svc in services.items()},
    }


@router.get("/health/detailed", summary="Detailed per-service health")
async def health_detailed() -> Dict[str, Any]:
    """Return full per-service health details including latency and version info.

    Runs all probes concurrently for fast aggregate response.
    """
    trino_result, airflow_result, om_result, pg_result = await asyncio.gather(
        _probe_trino(),
        _probe_airflow(),
        _probe_openmetadata(),
        _probe_postgres(),
        return_exceptions=False,
    )

    services = {
        "trino": trino_result,
        "airflow": airflow_result,
        "openmetadata": om_result,
        "postgres": pg_result,
    }

    return {
        "status": _overall_status(services),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services,
    }
