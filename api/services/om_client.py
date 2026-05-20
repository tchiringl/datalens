"""
OpenMetadata REST API client (OM 1.3.x /api/v1).

All methods are async and use httpx.AsyncClient.  The client handles JWT
token acquisition and refresh transparently — callers just await the method
they need.
"""

import os
from base64 import b64encode
from typing import Any, Dict, List, Optional

import httpx

OM_BASE_URL = (
    f"http://{os.getenv('OM_HOST', 'openmetadata-server')}:"
    f"{os.getenv('OM_PORT', '8585')}/api/v1"
)

_OM_USERNAME = os.environ.get("OM_USERNAME", "admin@openmetadata.org")
_OM_PASSWORD = os.environ["OM_PASSWORD"]

_TIMEOUT = 30.0


class OpenMetadataClient:
    """Async OpenMetadata API client with automatic token management."""

    def __init__(self) -> None:
        self.base_url: str = OM_BASE_URL
        self._token: Optional[str] = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def get_token(self) -> str:
        """Obtain (or return cached) a JWT bearer token from OM."""
        if self._token:
            return self._token

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            encoded_password = b64encode(_OM_PASSWORD.encode("utf-8")).decode("ascii")
            resp = await client.post(
                f"{self.base_url}/users/login",
                json={"email": _OM_USERNAME, "password": encoded_password},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("accessToken") or data.get("token", "")
        return self._token

    async def _headers(self) -> Dict[str, str]:
        token = await self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Authenticated GET helper. Retries once on 401 (token refresh)."""
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.base_url}{path}", headers=headers, params=params or {})
            if resp.status_code == 401:
                # Token expired — clear cache and retry once
                self._token = None
                headers = await self._headers()
                resp = await client.get(f"{self.base_url}{path}", headers=headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, body: Dict[str, Any]) -> Any:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{self.base_url}{path}", headers=headers, json=body)
            if resp.status_code == 401:
                self._token = None
                headers = await self._headers()
                resp = await client.post(f"{self.base_url}{path}", headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()

    async def _delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> None:
        headers = await self._headers()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(
                f"{self.base_url}{path}", headers=headers, params=params or {}
            )
            if resp.status_code == 401:
                self._token = None
                headers = await self._headers()
                resp = await client.delete(
                    f"{self.base_url}{path}", headers=headers, params=params or {}
                )
            # 404 is fine for idempotent deletes
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()

    # ------------------------------------------------------------------
    # Database Services (sources)
    # ------------------------------------------------------------------

    async def list_services(self, service_type: str = "databaseServices") -> List[Dict[str, Any]]:
        """List all database services registered in OpenMetadata."""
        data = await self._get(f"/services/{service_type}", params={"limit": 100})
        return data.get("data", [])

    async def get_service(self, service_name: str) -> Dict[str, Any]:
        """Return a single database service by name (FQN)."""
        return await self._get(f"/services/databaseServices/name/{service_name}")

    async def create_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new database service in OpenMetadata.

        *service_data* should conform to the OM CreateDatabaseService schema::

            {
                "name": "my_postgres",
                "serviceType": "Postgres",
                "connection": {
                    "config": {
                        "type": "Postgres",
                        "hostPort": "localhost:5432",
                        "username": "...",
                        "password": "...",
                        "database": "..."
                    }
                }
            }
        """
        return await self._post("/services/databaseServices", service_data)

    async def delete_service(self, service_name: str, recursive: bool = True) -> None:
        """Delete a database service (and optionally all child entities)."""
        # First resolve the service ID from its name
        try:
            svc = await self.get_service(service_name)
            service_id = svc.get("id")
        except httpx.HTTPStatusError:
            return  # Already gone

        if service_id:
            await self._delete(
                f"/services/databaseServices/{service_id}",
                params={"recursive": str(recursive).lower()},
            )

    # ------------------------------------------------------------------
    # Ingestion pipelines
    # ------------------------------------------------------------------

    async def list_ingestion_pipelines(self, service_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return ingestion pipelines, optionally filtered by service."""
        params: Dict[str, Any] = {"limit": 100}
        if service_name:
            params["service"] = service_name
        data = await self._get("/services/ingestionPipelines", params=params)
        return data.get("data", [])

    async def trigger_ingestion(self, pipeline_fqn: str) -> Dict[str, Any]:
        """Trigger an ingestion pipeline by its fully qualified name."""
        # Resolve FQN → ID
        pipeline = await self._get(f"/services/ingestionPipelines/name/{pipeline_fqn}")
        pipeline_id = pipeline.get("id")
        if not pipeline_id:
            raise ValueError(f"Ingestion pipeline not found: {pipeline_fqn}")
        return await self._post(f"/services/ingestionPipelines/trigger/{pipeline_id}", {})

    async def deploy_ingestion_pipeline(self, pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create and deploy an ingestion pipeline."""
        pipeline = await self._post("/services/ingestionPipelines", pipeline_data)
        pipeline_id = pipeline.get("id")
        if pipeline_id:
            await self._post(f"/services/ingestionPipelines/deploy/{pipeline_id}", {})
        return pipeline

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    async def list_tables(self, service_name: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Return tables, optionally filtered by service FQN prefix."""
        params: Dict[str, Any] = {"limit": limit, "fields": "columns,tableType,tableConstraints"}
        if service_name:
            params["database"] = service_name
        data = await self._get("/tables", params=params)
        return data.get("data", [])

    async def get_table(self, table_fqn: str) -> Dict[str, Any]:
        """Return a single table by FQN."""
        return await self._get(f"/tables/name/{table_fqn}", params={"fields": "columns,tableType,usageSummary"})

    # ------------------------------------------------------------------
    # Data Quality
    # ------------------------------------------------------------------

    async def get_dq_results(
        self,
        entity_fqn: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return test case results from OpenMetadata DQ.

        If *entity_fqn* is given, results are filtered to that table/column.
        """
        params: Dict[str, Any] = {
            "limit": limit,
            "fields": "testDefinition,testCaseResult,entityLink",
        }
        if entity_fqn:
            params["entityFQN"] = entity_fqn

        try:
            data = await self._get("/dataQuality/testCases", params=params)
            return data.get("data", [])
        except httpx.HTTPStatusError:
            return []

    async def get_test_case_result_history(self, test_case_fqn: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return historical results for a specific test case."""
        try:
            data = await self._get(
                f"/dataQuality/testCases/name/{test_case_fqn}/testCaseResult",
                params={"limit": limit},
            )
            return data.get("data", [])
        except httpx.HTTPStatusError:
            return []

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------

    async def get_lineage(
        self,
        entity_fqn: str,
        entity_type: str = "table",
        upstream_depth: int = 2,
        downstream_depth: int = 2,
    ) -> Dict[str, Any]:
        """Return upstream + downstream lineage for *entity_fqn*."""
        try:
            return await self._get(
                f"/lineage/{entity_type}/name/{entity_fqn}",
                params={
                    "upstreamDepth": upstream_depth,
                    "downstreamDepth": downstream_depth,
                },
            )
        except httpx.HTTPStatusError:
            return {"entity": {"name": entity_fqn}, "nodes": [], "edges": []}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Check OpenMetadata server availability via /tables endpoint."""
        try:
            data = await self._get("/tables", params={"limit": 1})
            return {"status": "healthy"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
