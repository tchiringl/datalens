"""
Airflow REST API client (Airflow 2.x /api/v1).

All methods are async and use httpx.AsyncClient.  Each public method returns
plain Python dicts / lists so callers (FastAPI route handlers) can serialise
them with Pydantic models as needed.
"""

import base64
import os
from typing import Any, Dict, List, Optional

import httpx

AIRFLOW_BASE_URL = (
    f"http://{os.getenv('AIRFLOW_HOST', 'airflow-webserver')}:8080/api/v1"
)

# Default HTTP timeout (seconds)
_TIMEOUT = 30.0


def _build_headers() -> Dict[str, str]:
    raw = f"{os.environ.get('AIRFLOW_ADMIN_USER', 'admin')}:{os.environ['AIRFLOW_ADMIN_PASSWORD']}"
    creds = base64.b64encode(raw.encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _map_status(airflow_state: Optional[str]) -> str:
    """Map Airflow internal states to simplified frontend states."""
    mapping = {
        "success": "success",
        "running": "running",
        "failed": "failed",
        "queued": "queued",
        "up_for_retry": "running",
        "up_for_reschedule": "queued",
        "upstream_failed": "failed",
        "skipped": "failed",
        "scheduled": "queued",
        "deferred": "queued",
        "removed": "failed",
        None: "unknown",
    }
    return mapping.get(airflow_state or "", "unknown")


class AirflowClient:
    """Async Airflow 2.x REST API client."""

    def __init__(self) -> None:
        self.base_url: str = AIRFLOW_BASE_URL
        self.headers: Dict[str, str] = _build_headers()

    # ------------------------------------------------------------------
    # DAG operations
    # ------------------------------------------------------------------

    async def list_dags(self, limit: int = 100, tags: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return a list of all DAG objects from Airflow.

        Each returned dict is the raw Airflow response enriched with a
        ``simplified_status`` key derived from the latest run state.
        """
        params: Dict[str, Any] = {"limit": limit, "only_active": False}
        if tags:
            params["tags"] = tags

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            dags: List[Dict[str, Any]] = data.get("dags", [])

        # Enrich each DAG with its latest run status
        enriched = []
        for dag in dags:
            dag_id = dag.get("dag_id", "")
            try:
                runs = await self.get_dag_runs(dag_id, limit=1)
                latest = runs[0] if runs else {}
                dag["latest_run_state"] = latest.get("state")
                dag["simplified_status"] = _map_status(latest.get("state"))
                dag["latest_run_id"] = latest.get("dag_run_id")
                dag["latest_start_date"] = latest.get("start_date")
                dag["latest_end_date"] = latest.get("end_date")
            except Exception:
                dag["latest_run_state"] = None
                dag["simplified_status"] = "unknown"
                dag["latest_run_id"] = None
                dag["latest_start_date"] = None
                dag["latest_end_date"] = None
            enriched.append(dag)

        return enriched

    async def get_dag(self, dag_id: str) -> Dict[str, Any]:
        """Return details for a single DAG, including its latest run."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            dag = resp.json()

        # Attach last-10 runs summary
        try:
            dag["recent_runs"] = await self.get_dag_runs(dag_id, limit=10)
        except Exception:
            dag["recent_runs"] = []

        return dag

    async def trigger_dag(
        self,
        dag_id: str,
        conf: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST a new DAG run and return the created DagRun object."""
        body: Dict[str, Any] = {"conf": conf or {}}
        if note:
            body["note"] = note

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/dags/{dag_id}/dagRuns",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            run = resp.json()

        run["simplified_status"] = _map_status(run.get("state"))
        return run

    # ------------------------------------------------------------------
    # DAG Run operations
    # ------------------------------------------------------------------

    async def get_dag_runs(
        self,
        dag_id: str,
        limit: int = 20,
        order_by: str = "-start_date",
    ) -> List[Dict[str, Any]]:
        """Return the last *limit* DAG runs for *dag_id*, newest first."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns",
                headers=self.headers,
                params={"limit": limit, "order_by": order_by},
            )
            resp.raise_for_status()
            data = resp.json()

        runs: List[Dict[str, Any]] = data.get("dag_runs", [])
        for run in runs:
            run["simplified_status"] = _map_status(run.get("state"))
            # Compute duration if both timestamps are present
            start = run.get("start_date")
            end = run.get("end_date")
            if start and end:
                from datetime import datetime, timezone

                fmt = "%Y-%m-%dT%H:%M:%S%z"
                try:
                    s = datetime.fromisoformat(start)
                    e = datetime.fromisoformat(end)
                    run["duration_seconds"] = (e - s).total_seconds()
                except (ValueError, TypeError):
                    run["duration_seconds"] = None
            else:
                run["duration_seconds"] = None
        return runs

    async def get_run_status(self, dag_id: str, run_id: str) -> Dict[str, Any]:
        """Return the status of a specific DAG run."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns/{run_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            run = resp.json()

        run["simplified_status"] = _map_status(run.get("state"))
        return run

    async def get_task_instances(self, dag_id: str, run_id: str) -> List[Dict[str, Any]]:
        """Return all task instances for a specific DAG run."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns/{run_id}/taskInstances",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("task_instances", [])

    # ------------------------------------------------------------------
    # Summary / aggregate helpers
    # ------------------------------------------------------------------

    async def get_status_summary(self) -> Dict[str, int]:
        """Return counts of DAG runs grouped by simplified status.

        Looks at the most-recent run of every DAG.
        """
        dags = await self.list_dags(limit=200)
        summary: Dict[str, int] = {
            "running": 0,
            "success": 0,
            "failed": 0,
            "queued": 0,
            "unknown": 0,
        }
        for dag in dags:
            status = dag.get("simplified_status", "unknown")
            summary[status] = summary.get(status, 0) + 1
        return summary

    async def health(self) -> Dict[str, Any]:
        """Return the Airflow /health endpoint response."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.base_url.rstrip('/api/v1')}/health",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()
