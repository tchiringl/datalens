"""
Sources router — manage data source registrations.

Endpoints
---------
GET    /api/sources                    list all sources
GET    /api/sources/{id}               get source + table list
POST   /api/sources                    register new source
DELETE /api/sources/{id}               remove source
POST   /api/sources/{id}/sync          trigger metadata sync
GET    /api/sources/{id}/tables        list tables for a source
GET    /api/sources/{id}/profile       profiling status for a source
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.om_client import OpenMetadataClient, get_om_client
from services.trino_client import TrinoClient

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

_SOURCE_TYPES = Literal["postgres", "redshift", "bigquery", "api", "iceberg"]
_SOURCE_STATUSES = Literal["connected", "error", "syncing", "unknown"]


class SourceCreate(BaseModel):
    name: str = Field(..., description="Unique source identifier / service name")
    type: _SOURCE_TYPES
    host: str
    port: int
    database: str
    username: str
    password: str
    description: Optional[str] = None


class SourceResponse(BaseModel):
    id: str
    name: str
    type: str
    status: _SOURCE_STATUSES
    table_count: int
    last_synced: Optional[datetime]
    description: Optional[str]


class SourceDetail(SourceResponse):
    tables: List[Dict[str, Any]] = []
    connection_info: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map our simplified type names to OpenMetadata serviceType values
_OM_SERVICE_TYPE_MAP = {
    "postgres": "Postgres",
    "redshift": "Redshift",
    "bigquery": "BigQuery",
    "api": "CustomDatabase",
    "iceberg": "Iceberg",
}


def _build_om_connection_config(source: SourceCreate) -> Dict[str, Any]:
    """Construct the OM CreateDatabaseService connection body."""
    svc_type = _OM_SERVICE_TYPE_MAP.get(source.type, "Postgres")

    config: Dict[str, Any] = {
        "type": svc_type,
        "username": source.username,
        "password": source.password,
        "database": source.database,
    }

    if source.type in ("postgres", "redshift"):
        config["hostPort"] = f"{source.host}:{source.port}"
    elif source.type == "bigquery":
        config["projectId"] = source.database  # BigQuery uses projectId

    return {
        "name": source.name,
        "serviceType": svc_type,
        "description": source.description or "",
        "connection": {"config": config},
    }


def _om_service_to_response(svc: Dict[str, Any]) -> SourceResponse:
    """Convert an OM databaseService object to our SourceResponse model."""
    svc_type_raw: str = svc.get("serviceType", "")
    # Reverse-map OM type to our simplified type
    reverse_map = {v: k for k, v in _OM_SERVICE_TYPE_MAP.items()}
    simplified_type = reverse_map.get(svc_type_raw, svc_type_raw.lower())

    # OM stores last ingestion timestamp in pipelines; use updatedAt as proxy
    updated_at_ms: Optional[int] = svc.get("updatedAt")
    last_synced: Optional[datetime] = None
    if updated_at_ms:
        try:
            last_synced = datetime.fromtimestamp(updated_at_ms / 1000, tz=timezone.utc)
        except (ValueError, OSError):
            pass

    return SourceResponse(
        id=svc.get("id", svc.get("name", "")),
        name=svc.get("name", ""),
        type=simplified_type,
        status="connected",
        table_count=0,  # populated separately when querying tables
        last_synced=last_synced,
        description=svc.get("description"),
    )


async def _count_tables(om: OpenMetadataClient, service_name: str) -> int:
    """Return table count for *service_name* without fetching all columns."""
    try:
        tables = await om.list_tables(service_name=service_name, limit=200)
        return len(tables)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("", response_model=List[SourceResponse], summary="List all data sources")
async def list_sources() -> List[SourceResponse]:
    """Return all database services registered in OpenMetadata."""
    om = get_om_client()
    try:
        services = await om.list_services()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenMetadata unreachable: {exc}",
        )

    # Fetch table counts concurrently
    async def _enrich(svc: Dict[str, Any]) -> SourceResponse:
        resp = _om_service_to_response(svc)
        count = await _count_tables(om, svc.get("name", ""))
        return resp.model_copy(update={"table_count": count})

    results = await asyncio.gather(*[_enrich(s) for s in services], return_exceptions=True)
    return [r for r in results if isinstance(r, SourceResponse)]


@router.get("/{source_id}", response_model=SourceDetail, summary="Get source details")
async def get_source(source_id: str) -> SourceDetail:
    """Return details for a single source including its table list."""
    om = get_om_client()
    try:
        svc = await om.get_service(source_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
        raise HTTPException(status_code=502, detail=f"OpenMetadata error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenMetadata unreachable: {exc}")

    base = _om_service_to_response(svc)

    try:
        tables = await om.list_tables(service_name=svc.get("name", ""), limit=200)
    except Exception:
        tables = []

    return SourceDetail(
        **base.model_dump(),
        table_count=len(tables),
        tables=tables,
        connection_info={
            "serviceType": svc.get("serviceType"),
            "connection": svc.get("connection", {}),
        },
    )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED,
             summary="Register a new data source")
async def create_source(source: SourceCreate) -> SourceResponse:
    """Register a new data source.

    Steps
    -----
    1. Validate the connection by running a lightweight Trino query (if postgres).
    2. Register the service in OpenMetadata.
    3. Return the created source record.
    """
    # Step 1 — validate connection via Trino (best-effort for postgres sources)
    if source.type == "postgres":
        trino = TrinoClient()
        loop = asyncio.get_event_loop()
        try:
            connected = await loop.run_in_executor(None, trino.test_connection, source.name)
            if not connected:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Cannot reach catalog '{source.name}' via Trino. "
                        "Ensure the Trino catalog is configured before registering."
                    ),
                )
        except HTTPException:
            raise
        except Exception as exc:
            # Trino not reachable — warn but don't block registration
            pass

    # Step 2 — register in OpenMetadata
    om = get_om_client()
    service_body = _build_om_connection_config(source)
    try:
        created = await om.create_service(service_body)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A source named '{source.name}' already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenMetadata error: {exc.response.text}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenMetadata unreachable: {exc}",
        )

    return _om_service_to_response(created)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove a data source")
async def delete_source(source_id: str) -> None:
    """Delete a source from OpenMetadata (and all its child entities)."""
    om = get_om_client()
    try:
        await om.delete_service(source_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to delete source: {exc}",
        )


@router.post("/{source_id}/sync", summary="Trigger metadata sync")
async def sync_source(source_id: str) -> Dict[str, Any]:
    """Trigger an OpenMetadata ingestion pipeline for this source.

    The endpoint looks for a pipeline whose name starts with *source_id*.
    If none is found it returns a 404.
    """
    om = get_om_client()
    try:
        pipelines = await om.list_ingestion_pipelines(service_name=source_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenMetadata unreachable: {exc}")

    if not pipelines:
        raise HTTPException(
            status_code=404,
            detail=f"No ingestion pipeline found for source '{source_id}'.",
        )

    # Trigger the first matching pipeline
    pipeline = pipelines[0]
    pipeline_fqn: str = pipeline.get("fullyQualifiedName", pipeline.get("name", ""))

    try:
        result = await om.trigger_ingestion(pipeline_fqn)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to trigger ingestion: {exc}")

    return {
        "source_id": source_id,
        "pipeline": pipeline_fqn,
        "triggered": True,
        "result": result,
    }


@router.get("/{source_id}/tables", summary="List tables for a source")
async def list_source_tables(source_id: str) -> Dict[str, Any]:
    """Return all tables discovered for this source."""
    om = get_om_client()
    try:
        tables = await om.list_tables(service_name=source_id, limit=500)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenMetadata unreachable: {exc}")

    return {
        "source_id": source_id,
        "table_count": len(tables),
        "tables": tables,
    }


@router.get("/{source_id}/profile", summary="Get profiling status for a source")
async def get_source_profile(source_id: str) -> Dict[str, Any]:
    """Return profiling status and basic column stats for all tables in this source.

    Queries Trino for row counts and OpenMetadata for column-level profile data.
    """
    om = get_om_client()
    trino = TrinoClient()

    try:
        tables = await om.list_tables(service_name=source_id, limit=200)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenMetadata unreachable: {exc}")

    profile_results: List[Dict[str, Any]] = []

    loop = asyncio.get_event_loop()
    for table in tables:
        fqn: str = table.get("fullyQualifiedName", "")
        parts = fqn.split(".")  # catalog.schema.table or service.db.schema.table
        row_count: Optional[int] = None

        if len(parts) >= 3:
            try:
                # Try to get row count from Trino
                catalog, schema, tbl = parts[-3], parts[-2], parts[-1]
                row_count = await loop.run_in_executor(
                    None, trino.get_table_row_count, catalog, schema, tbl
                )
            except Exception:
                pass

        profile_results.append(
            {
                "table_fqn": fqn,
                "table_name": table.get("name", ""),
                "row_count": row_count,
                "column_count": len(table.get("columns", [])),
                "profile_available": row_count is not None,
            }
        )

    return {
        "source_id": source_id,
        "profiled_tables": len([p for p in profile_results if p["profile_available"]]),
        "total_tables": len(profile_results),
        "tables": profile_results,
    }
