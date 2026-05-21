"""
OpenMetadata REST client for schema extraction.
OM API base: http://{host}:{port}/api/v1
Auth: JWT via POST /users/login with base64-encoded password.
"""

import base64
import asyncio
import httpx
from typing import Optional


class OpenMetadataClient:
    def __init__(self, host: str = "localhost", port: int = 8588,
                 username: str = "admin", password: str = "admin"):
        self.base_url = f"http://{host}:{port}/api/v1"
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        await self._get_token()
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _get_token(self) -> str:
        """Authenticate and cache JWT token."""
        # OM 1.5.x uses basic auth login
        encoded_password = base64.b64encode(self.password.encode()).decode()
        resp = await self._client.post(
            f"{self.base_url}/users/login",
            json={"email": f"{self.username}@open-metadata.org", "password": encoded_password}
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("accessToken") or data.get("token")
        return self._token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make authenticated request, auto-refresh token on 401."""
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        resp = await self._client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        if resp.status_code == 401:
            await self._get_token()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = await self._client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}

    async def health(self) -> bool:
        """Check if OM server is healthy."""
        try:
            resp = await self._client.get(f"{self.base_url}/system/status", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def get_service(self, service_name: str) -> Optional[dict]:
        """Get a database service by name, returns None if not found."""
        try:
            result = await self._request("GET", f"/services/databaseServices/name/{service_name}")
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_postgres_service(self, service_name: str, host: str, port: int,
                                       database: str, user: str, password: str) -> dict:
        """Register a PostgreSQL database service in OpenMetadata."""
        payload = {
            "name": service_name,
            "displayName": service_name,
            "serviceType": "Postgres",
            "connection": {
                "config": {
                    "type": "Postgres",
                    "username": user,
                    "authType": {"password": password},
                    "hostPort": f"{host}:{port}",
                    "database": database,
                }
            }
        }
        return await self._request("POST", "/services/databaseServices", json=payload)

    async def get_or_create_service(self, service_name: str, host: str, port: int,
                                     database: str, user: str, password: str) -> dict:
        """Get existing service or create it."""
        existing = await self.get_service(service_name)
        if existing:
            print(f"Service '{service_name}' already exists.")
            return existing
        print(f"Creating service '{service_name}'...")
        return await self.create_postgres_service(service_name, host, port, database, user, password)

    async def list_ingestion_pipelines(self, service_name: str) -> list:
        """List ingestion pipelines for a service."""
        result = await self._request("GET", "/services/ingestionPipelines",
                                      params={"service": service_name, "limit": 50})
        return result.get("data", [])

    async def create_metadata_pipeline(self, service_id: str, service_name: str) -> dict:
        """Create a metadata ingestion pipeline for the service."""
        payload = {
            "name": f"{service_name}-metadata-pipeline",
            "displayName": f"{service_name} Metadata Pipeline",
            "pipelineType": "metadata",
            "service": {"id": service_id, "type": "databaseService"},
            "sourceConfig": {
                "config": {
                    "type": "DatabaseMetadata",
                    "markDeletedTables": False,
                    "markDeletedStoredProcedures": False,
                    "includeTables": True,
                    "includeViews": True,
                    "queryLogDuration": 1,
                }
            },
            "airflowConfig": {
                "scheduleInterval": None,
                "startDate": "2025-01-01T00:00:00Z",
            }
        }
        return await self._request("POST", "/services/ingestionPipelines", json=payload)

    async def trigger_ingestion(self, pipeline_id: str) -> dict:
        """Trigger an ingestion pipeline run."""
        return await self._request("POST", f"/services/ingestionPipelines/trigger/{pipeline_id}")

    async def get_pipeline_status(self, pipeline_id: str) -> str:
        """Get current pipeline run status: running|success|failed|unknown."""
        try:
            result = await self._request("GET", f"/services/ingestionPipelines/{pipeline_id}")
            runs = result.get("pipelineStatuses", {})
            if isinstance(runs, list) and runs:
                return runs[-1].get("pipelineState", "unknown")
            return "unknown"
        except Exception:
            return "unknown"

    async def poll_ingestion_completion(self, pipeline_id: str, timeout: int = 180, interval: int = 5) -> str:
        """Poll until ingestion completes or times out. Returns 'success', 'failed', or 'timeout'."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            status = await self.get_pipeline_status(pipeline_id)
            print(f"  Pipeline status: {status}")
            if status in ("success", "failed", "partialSuccess"):
                return status
            await asyncio.sleep(interval)
        return "timeout"

    async def list_tables(self, service_name: str, limit: int = 500) -> list[dict]:
        """
        List all tables for a service with column metadata.
        Returns list of dicts: {name, fqn, columns: [{name, dataType, nullable}]}
        """
        params = {
            "service": service_name,
            "limit": limit,
            "fields": "columns,tableType",
            "include": "non-deleted",
        }
        result = await self._request("GET", "/tables", params=params)
        tables = result.get("data", [])
        output = []
        for t in tables:
            columns = []
            for col in t.get("columns", []):
                columns.append({
                    "name": col.get("name", ""),
                    "dataType": col.get("dataType", "VARCHAR"),
                    "nullable": col.get("constraint", "") != "NOT_NULL",
                    "description": col.get("description", ""),
                })
            output.append({
                "name": t.get("name", ""),
                "fqn": t.get("fullyQualifiedName", ""),
                "columns": columns,
            })
        return output

    async def run_full_ingestion(self, service_name: str, pg_host: str, pg_port: int,
                                  pg_db: str, pg_user: str, pg_password: str) -> list[dict]:
        """
        Full flow: ensure service exists → ensure pipeline exists → trigger → poll → return tables.
        """
        service = await self.get_or_create_service(service_name, pg_host, pg_port, pg_db, pg_user, pg_password)
        service_id = service["id"]

        pipelines = await self.list_ingestion_pipelines(service_name)
        if pipelines:
            pipeline = pipelines[0]
            print(f"Using existing pipeline: {pipeline['name']}")
        else:
            print("Creating metadata pipeline...")
            pipeline = await self.create_metadata_pipeline(service_id, service_name)

        pipeline_id = pipeline["id"]
        print(f"Triggering ingestion pipeline {pipeline_id}...")
        await self.trigger_ingestion(pipeline_id)

        print("Polling ingestion status...")
        status = await self.poll_ingestion_completion(pipeline_id, timeout=180, interval=5)
        print(f"Ingestion completed with status: {status}")

        print("Fetching tables from OpenMetadata...")
        tables = await self.list_tables(service_name)
        print(f"Found {len(tables)} tables.")
        return tables
