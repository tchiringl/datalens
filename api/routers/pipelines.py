"""
Pipelines router — proxy to Airflow REST API.

Endpoints
---------
GET  /api/pipelines                       list all DAGs
GET  /api/pipelines/status/summary        count by simplified status
GET  /api/pipelines/{dag_id}              get DAG details
POST /api/pipelines/{dag_id}/trigger      trigger a new DAG run
GET  /api/pipelines/{dag_id}/runs         last N runs
GET  /api/pipelines/{dag_id}/runs/{run_id} specific run status
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services.airflow_client import AirflowClient

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class DAGRun(BaseModel):
    run_id: str
    dag_id: str
    status: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    triggered_by: str = "unknown"


class TriggerRequest(BaseModel):
    conf: Optional[Dict[str, Any]] = {}
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _airflow_run_to_dag_run(run: Dict[str, Any]) -> DAGRun:
    """Map an Airflow dagRun object to our DAGRun model."""
    triggered_by: str = "unknown"
    run_type = run.get("run_type", "")
    triggered_by_map = {
        "scheduled": "scheduler",
        "manual": "user",
        "backfill": "backfill",
        "dataset_triggered": "dataset",
    }
    triggered_by = triggered_by_map.get(run_type, run_type or "unknown")

    # Parse ISO datetime strings safely
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    return DAGRun(
        run_id=run.get("dag_run_id", run.get("run_id", "")),
        dag_id=run.get("dag_id", ""),
        status=run.get("simplified_status", run.get("state", "unknown")),
        start_date=_parse_dt(run.get("start_date")),
        end_date=_parse_dt(run.get("end_date")),
        duration_seconds=run.get("duration_seconds"),
        triggered_by=triggered_by,
    )


def _handle_airflow_error(exc: Exception, dag_id: Optional[str] = None) -> HTTPException:
    """Convert an httpx error from the Airflow client to an HTTPException."""
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 404:
            detail = f"DAG '{dag_id}' not found in Airflow." if dag_id else "Resource not found."
            return HTTPException(status_code=404, detail=detail)
        return HTTPException(
            status_code=502,
            detail=f"Airflow returned HTTP {exc.response.status_code}: {exc.response.text[:300]}",
        )
    return HTTPException(
        status_code=502,
        detail=f"Airflow unreachable: {exc}",
    )


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


# NOTE: /status/summary must be defined BEFORE /{dag_id} to avoid FastAPI
# treating "status" as a dag_id path parameter.
@router.get("/status/summary", summary="Pipeline run count by status")
async def pipelines_status_summary() -> Dict[str, Any]:
    """Return the count of most-recent DAG runs grouped by simplified status.

    Statuses: running | success | failed | queued | unknown
    """
    client = AirflowClient()
    try:
        summary = await client.get_status_summary()
    except Exception as exc:
        raise _handle_airflow_error(exc)
    return summary


@router.get("", summary="List all DAGs")
async def list_pipelines() -> List[Dict[str, Any]]:
    """Return all DAGs from Airflow, enriched with their latest run status."""
    client = AirflowClient()
    try:
        dags = await client.list_dags()
    except Exception as exc:
        raise _handle_airflow_error(exc)
    return dags


@router.get("/{dag_id}", summary="Get DAG details")
async def get_pipeline(dag_id: str) -> Dict[str, Any]:
    """Return details for a single DAG including its 10 most-recent runs."""
    client = AirflowClient()
    try:
        dag = await client.get_dag(dag_id)
    except Exception as exc:
        raise _handle_airflow_error(exc, dag_id=dag_id)
    return dag


@router.post("/{dag_id}/trigger", summary="Trigger a new DAG run",
             status_code=status.HTTP_201_CREATED)
async def trigger_pipeline(dag_id: str, body: TriggerRequest) -> DAGRun:
    """Trigger a new run of *dag_id* with optional configuration payload."""
    client = AirflowClient()
    try:
        run = await client.trigger_dag(dag_id, conf=body.conf or {}, note=body.note)
    except Exception as exc:
        raise _handle_airflow_error(exc, dag_id=dag_id)
    return _airflow_run_to_dag_run(run)


@router.get("/{dag_id}/runs", summary="Get last N DAG runs")
async def list_pipeline_runs(dag_id: str, limit: int = 20) -> List[DAGRun]:
    """Return the last *limit* runs for *dag_id*, newest first."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100.")
    client = AirflowClient()
    try:
        runs = await client.get_dag_runs(dag_id, limit=limit)
    except Exception as exc:
        raise _handle_airflow_error(exc, dag_id=dag_id)
    return [_airflow_run_to_dag_run(r) for r in runs]


@router.get("/{dag_id}/runs/{run_id}", summary="Get a specific run status",
            response_model=DAGRun)
async def get_pipeline_run(dag_id: str, run_id: str) -> DAGRun:
    """Return the status and metadata for a specific DAG run."""
    client = AirflowClient()
    try:
        run = await client.get_run_status(dag_id, run_id)
    except Exception as exc:
        raise _handle_airflow_error(exc, dag_id=dag_id)
    return _airflow_run_to_dag_run(run)
