# DataLens — Developer Guide

This guide walks a new developer through standing up the full DataLens stack from scratch. No prior familiarity with the codebase is assumed.

---

## Prerequisites

Before you begin, ensure the following are installed and available:

- **Docker Desktop 4.x or later** (or Docker Engine + Compose plugin on Linux)
- **16 GB RAM minimum** — the full stack runs 13 containers; fewer resources will cause containers to OOM-kill each other
- **The following ports must be free** on your machine before running `make up`:

| Port | Service |
|------|---------|
| 3000 | React frontend |
| 5432 | PostgreSQL |
| 8000 | FastAPI backend |
| 8080 | Trino query engine |
| 8082 | Airflow webserver |
| 8083 | Airflow scheduler metrics |
| 8585 | OpenMetadata server |
| 9000 | MinIO S3 API |
| 9001 | MinIO console |
| 9200 | Elasticsearch |

Check for conflicts with `lsof -i :<port>` or `ss -tlnp | grep <port>`.

---

## First-Time Setup

### 1. Clone the repository

```bash
git clone <repo-url> datalens
cd datalens
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in the required secrets. The following variables have no safe default and **must** be set:

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Password for the PostgreSQL `datalens` user |
| `MINIO_ROOT_PASSWORD` | MinIO root account password (min 8 chars) |
| `AIRFLOW__CORE__FERNET_KEY` | 32-byte base64 key for Airflow secret encryption — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SECRET_KEY` | FastAPI session secret — any long random string |
| `OM_PASSWORD` | OpenMetadata admin password |
| `AIRFLOW_ADMIN_PASSWORD` | Airflow UI admin password |

### 3. Start all services

```bash
make up
```

This starts 13 Docker containers in detached mode. On first run, Docker will pull images — allow 5–10 minutes on a typical connection.

### 4. Wait for OpenMetadata to be ready

OpenMetadata takes approximately 2 minutes to complete its database migrations and become healthy. Run the validation script to check:

```bash
make validate
```

All services should show `[OK]`. If OpenMetadata shows `[FAIL]`, wait 30 seconds and try again. The other services start faster and should be green within 60 seconds.

### 5. Bootstrap OpenMetadata tokens

The ingestion configs need a JWT token from OpenMetadata. Run:

```bash
export OM_PASSWORD=<your-password>
make bootstrap-om
```

This calls `scripts/bootstrap_om_tokens.sh`, which logs in to OpenMetadata, retrieves a JWT, and writes it into the ingestion YAML configs under `openmetadata/ingestion/`.

### 6. Open the application

Navigate to [http://localhost:3000](http://localhost:3000). The frontend communicates with the FastAPI backend at [http://localhost:8000](http://localhost:8000). API documentation (Swagger UI) is at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Project Structure

```
datalens/
├── api/                        # FastAPI backend
│   ├── main.py                 # App factory, CORS config, router mounts
│   ├── requirements.txt
│   ├── routers/                # One file per feature domain
│   │   ├── health.py           # GET /health, /health/detailed
│   │   ├── sources.py          # Data source CRUD, sync, profile
│   │   ├── pipelines.py        # Airflow DAG proxy
│   │   ├── dq.py               # Data quality aggregation
│   │   ├── cdm.py              # CDM exploration and lineage
│   │   ├── assessment.py       # YData profiling HTML reports
│   │   └── mock.py             # Mock data endpoints
│   └── services/               # Async clients for external services
│       ├── om_client.py        # OpenMetadata REST client (JWT auto-refresh)
│       ├── airflow_client.py   # Airflow REST client
│       ├── trino_client.py     # Trino Python client wrapper
│       └── assessment_service.py
├── frontend/                   # React 18 + Vite 5 + Tailwind CSS
│   ├── src/
│   └── package.json
├── dbt_project/                # dbt-trino transformation project
│   ├── dbt_project.yml
│   ├── profiles.yml            # Points to trino:8080 (internal Docker hostname)
│   ├── models/
│   │   ├── staging/            # Raw source cleaning
│   │   ├── cdm/                # Core Data Model (facts + dimensions)
│   │   └── profiling/          # Column-level statistics models
│   ├── macros/
│   │   └── alert_high_null_rate.sql  # Custom DQ test macro
│   └── packages.yml            # dbt_expectations, dbt_utils
├── airflow/
│   └── dags/                   # DAG definitions
├── openmetadata/
│   └── ingestion/              # OM ingestion YAML configs
├── docker-compose.yml          # All 13 services defined here
├── Makefile                    # Developer shortcuts
└── .env.example                # Environment variable template
```

---

## Service URLs

| Service | URL | Default credentials |
|---------|-----|---------------------|
| React frontend | http://localhost:3000 | — |
| FastAPI (Swagger) | http://localhost:8000/docs | — |
| Trino UI | http://localhost:8080 | user: `admin`, no password |
| Airflow | http://localhost:8082 | user: `admin`, password: `AIRFLOW_ADMIN_PASSWORD` |
| OpenMetadata | http://localhost:8585 | user: `admin@openmetadata.org`, password: `OM_PASSWORD` |
| MinIO console | http://localhost:9001 | user: `MINIO_ROOT_USER`, password: `MINIO_ROOT_PASSWORD` |
| Elasticsearch | http://localhost:9200 | — |

---

## Key Commands

```bash
make up             # Start all 13 services (detached)
make down           # Stop all containers (volumes preserved)
make reset          # Stop containers AND delete all data volumes (irreversible)
make logs           # Tail logs from all services (Ctrl-C to exit)
make status         # Show running container status (docker compose ps)
make validate       # Curl-check health endpoints for all services
make bootstrap-om   # Write OpenMetadata JWT into ingestion configs
make trino-cli      # Open interactive Trino SQL shell
make dbt-run        # Run all dbt models inside the API container
make dbt-test       # Run all dbt tests inside the API container
```

---

## How to Add a New dbt Model

1. **Create the SQL file** in the appropriate layer directory:
   - `dbt_project/models/staging/` for raw source cleaning
   - `dbt_project/models/cdm/` for fact and dimension tables
   - `dbt_project/models/profiling/` for statistical profiling models

2. **Add an entry to `schema.yml`** in the same directory. At minimum, define `name` and add `not_null` and `unique` tests to your primary key column:

   ```yaml
   - name: your_model_name
     description: "What this model represents."
     columns:
       - name: id_column
         tests:
           - not_null
           - unique
   ```

3. **Run the model** to verify it compiles and executes:

   ```bash
   make dbt-run
   # or to run only your model:
   docker compose exec api bash -c "cd /dbt && dbt run --select your_model_name"
   ```

4. **Run the tests** to verify the assertions pass:

   ```bash
   docker compose exec api bash -c "cd /dbt && dbt test --select your_model_name"
   ```

5. **Commit** the `.sql` file and the updated `schema.yml` together.

---

## How to Add a New API Endpoint

The FastAPI app uses a router-per-domain pattern. All routers are in `api/routers/` and mounted in `api/main.py`.

**Pattern for a new endpoint:**

```python
# api/routers/your_domain.py
import logging
from fastapi import APIRouter, Depends
from api.routers._pagination import pagination
from api.services.om_client import get_om_client, OpenMetadataClient

router = APIRouter(prefix="/your-domain", tags=["your-domain"])
_log = logging.getLogger(__name__)

@router.get("/items")
async def list_items(
    p: dict = Depends(pagination),
    om: OpenMetadataClient = Depends(get_om_client),
):
    _log.info("list_items called, page=%s", p["page"])
    result = await om.get("/v1/your-endpoint", params=p)
    return result
```

Key conventions:
- Use `get_om_client()` as a FastAPI dependency — it returns a singleton client and handles JWT auto-refresh on 401
- Use `Depends(pagination)` for any list endpoint to get consistent `limit`/`offset`/`page` query parameters
- Always add a `_log.info()` call at the start of each handler so requests appear in the API logs
- Mount the new router in `api/main.py`: `app.include_router(your_domain.router)`

---

## Common Startup Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| API returns 401 on OpenMetadata calls immediately after `make up` | OM is still running database migrations | Wait 2 minutes, then run `make validate` until OM shows `[OK]` |
| `airflow-init` container exits with a non-zero code | Fernet key not set or malformed | Verify `AIRFLOW__CORE__FERNET_KEY` in `.env` is a valid 32-byte base64 string; regenerate with the Python command in the setup section |
| Trino queries fail with "Schema not found" or Hive Metastore errors | MinIO bucket or Iceberg catalog not yet initialised | Run `make reset` and `make up` to let the MinIO init container recreate the buckets from scratch |
| MinIO shows empty buckets after `make up` | Init container ran before MinIO was fully ready | Run `docker compose restart minio-init` (or whichever init service is defined in docker-compose.yml) |
| API container fails to start with `KeyError: 'OM_PASSWORD'` | `.env` file is missing or uses wrong variable name | Ensure `.env` contains `OM_PASSWORD=...` exactly — not `OM_ADMIN_PASSWORD` or any other variation |

---

## Version Upgrade Policy

- **Pin everything.** Every image in `docker-compose.yml` uses an explicit version tag. Never change a tag to `latest` — `latest` is a moving target that breaks reproducibility.
- **MinIO is archived.** The version of MinIO used in this project is from the `RELEASE.2024-01-xx` series. The open-source MinIO project changed its licence; check the comment in `docker-compose.yml` before upgrading.
- **Test before upgrading.** Run `make reset && make up && make validate && make dbt-test` after any image version bump to catch regressions before committing.
- **dbt packages** (`dbt_expectations`, `dbt_utils`) are pinned in `dbt_project/packages.yml`. Update them intentionally, not automatically.
