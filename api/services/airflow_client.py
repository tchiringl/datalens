"""
Airflow REST API client (Airflow 3.x /api/v2).

All methods are async and use httpx.AsyncClient.  Each public method returns
plain Python dicts / lists so callers (FastAPI route handlers) can serialise
them with Pydantic models as needed.

Auth: Airflow 3.x uses JWT tokens. Tokens are fetched via POST /api/v2/auth/token
and cached per-instance with a 1-hour TTL (Airflow default expiry).
"""

import os
import time
from typing import Any, Dict, List, Optional

import httpx

_HOST = os.getenv("AIRFLOW_HOST", "airflow-api-server")
_BASE_HOST = f"http://{_HOST}:8080"
AIRFLOW_BASE_URL = f"{_BASE_HOST}/api/v2"

_TIMEOUT = 30.0


class AirflowClient:
    """Async Airflow 3.x REST API client with JWT auth."""

    def __init__(self) -> None:
        self._base_host: str = _BASE_HOST
        self.base_url: str = AIRFLOW_BASE_URL
        self._username: str = os.getenv("AIRFLOW_ADMIN_USER", "admin")
        self._password: str = os.environ["AIRFLOW_ADMIN_PASSWORD"]
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def _get_headers(self) -> Dict[str, str]:
        """Return auth headers, fetching/refreshing JWT token as needed."""
        if not self._token or time.time() > self._token_expires_at - 60:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/auth/token",
                    json={"username": self._username, "password": self._password},
                )
                resp.raise_for_status()
                self._token = resp.json()["access_token"]
                self._token_expires_at = time.time() + 3600
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _map_status(self, airflow_state: Optional[str]) -> str:
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

    # ------------------------------------------------------------------
    # DAG operations
    # ------------------------------------------------------------------

    async def list_dags(self, limit: int = 100, tags: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return a list of all DAG objects enriched with latest run state."""
        params: Dict[str, Any] = {"limit": limit}
        if tags:
            # v2 uses exploded form: ?tags=a&tags=b
            params["tags"] = tags.split(",") if isinstance(tags, str) else tags

        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            dags: List[Dict[str, Any]] = resp.json().get("dags", [])

        enriched = []
        for dag in dags:
            dag_id = dag.get("dag_id", "")
            try:
                runs = await self.get_dag_runs(dag_id, limit=1)
                latest = runs[0] if runs else {}
                dag["latest_run_state"] = latest.get("state")
                dag["simplified_status"] = self._map_status(latest.get("state"))
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
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}",
                headers=headers,
            )
            resp.raise_for_status()
            dag = resp.json()

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

        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/dags/{dag_id}/dagRuns",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            run = resp.json()

        run["simplified_status"] = self._map_status(run.get("state"))
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
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns",
                headers=headers,
                params={"limit": limit, "order_by": order_by},
            )
            resp.raise_for_status()
            runs: List[Dict[str, Any]] = resp.json().get("dag_runs", [])

        for run in runs:
            run["simplified_status"] = self._map_status(run.get("state"))
            start = run.get("start_date")
            end = run.get("end_date")
            if start and end:
                from datetime import datetime
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
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns/{run_id}",
                headers=headers,
            )
            resp.raise_for_status()
            run = resp.json()

        run["simplified_status"] = self._map_status(run.get("state"))
        return run

    async def get_task_instances(self, dag_id: str, run_id: str) -> List[Dict[str, Any]]:
        """Return all task instances for a specific DAG run."""
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self.base_url}/dags/{dag_id}/dagRuns/{run_id}/taskInstances",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("task_instances", [])

    # ------------------------------------------------------------------
    # Summary / aggregate helpers
    # ------------------------------------------------------------------

    async def get_status_summary(self) -> Dict[str, int]:
        """Return counts of DAG runs grouped by simplified status."""
        dags = await self.list_dags(limit=200)
        summary: Dict[str, int] = {
            "running": 0, "success": 0, "failed": 0, "queued": 0, "unknown": 0,
        }
        for dag in dags:
            status = dag.get("simplified_status", "unknown")
            summary[status] = summary.get(status, 0) + 1
        return summary

    async def health(self) -> Dict[str, Any]:
        """Return the Airflow /health endpoint response."""
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_host}/health",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
