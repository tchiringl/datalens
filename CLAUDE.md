# DataLens — CLAUDE.md

## Project Overview

Retail data lakehouse POC. Federated query (Trino) + data governance (OpenMetadata) + transformation (dbt) + orchestration (Airflow). FastAPI backend + React frontend.

Renamed from DataHub → Data Lens (commit 47e330a). Active dev on `feature_add` branch.

## Architecture

```
PostgreSQL (retail DB)
    └─► Trino (federated query engine) ◄─── Iceberg/MinIO (S3-compatible)
            └─► dbt-trino (CDM transforms)
                    └─► Airflow (orchestration)
                            └─► OpenMetadata (governance, lineage, DQ)
                                    └─► Elasticsearch (search index)

FastAPI (port 8000) ─► proxies all above
React/Vite (port 3000) ─► consumes FastAPI
```

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Query Engine | Trino | 481 |
| Storage | MinIO + Apache Iceberg | RELEASE.2025-09-07T16-13-09Z (final community release per Docker Hub) |
| Transform | dbt-trino | 1.9.2 |
| Metastore | Apache Hive standalone metastore | 4.2.0 |
| Orchestration | Airflow | 3.2.1 |
| Governance | OpenMetadata | 1.12.8 |
| Search | OpenSearch | 2.19.5 |
| Database | PostgreSQL | 18.4-alpine |
| API | FastAPI + uvicorn (Python 3.13-slim-bookworm) | 0.115.0 |
| Frontend | React 18.3 + Vite 5.4 + Tailwind CSS 3.4 (Node 22-alpine3.23) | - |
| UI Components | Radix UI + Recharts + React Query | - |

## Service URLs (local)

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 (Swagger: /docs) |
| Trino | http://localhost:8080 |
| Airflow | http://localhost:8082 |
| OpenMetadata | http://localhost:8585 |
| MinIO Console | http://localhost:9001 |
| PostgreSQL | localhost:5432 |

## Key Commands

```bash
# Docker Compose
make up          # Start all 13 services
make down        # Stop all services
make reset       # Full reset (wipe volumes)
make logs        # Tail all service logs
make status      # Service health status

# Trino
make trino-cli   # Open Trino CLI

# dbt
make dbt-run     # Run all dbt models
make dbt-test    # Run dbt tests

# Validation
make validate    # Run validation checklist
```

## API Structure

```
api/
├── main.py               # FastAPI app, CORS, router mounts
├── requirements.txt      # FastAPI, trino-python-client, httpx, pydantic, SQLAlchemy
├── routers/
│   ├── health.py         # GET /health, /health/detailed — concurrent probes, 8s timeout each
│   ├── sources.py        # Data source CRUD + sync + profile via OpenMetadata
│   ├── pipelines.py      # Airflow DAG proxy (list, trigger, history)
│   ├── dq.py             # Data quality aggregation from OpenMetadata
│   ├── cdm.py            # CDM layer exploration (models, columns, lineage)
│   ├── _pagination.py    # Reusable limit/offset pagination dependency
│   └── mock.py           # Mock data endpoints
└── services/
    ├── om_client.py      # OpenMetadataClient — async REST, JWT token mgmt, auto-refresh on 401
    ├── airflow_client.py # AirflowClient — async Airflow REST
    └── trino_client.py   # TrinoClient — sync trino-python-client wrapper
```

## dbt Profiling Layer

ydata-profiling has been replaced with dbt-native profiling models. The profiling layer runs as part of the Airflow DAG after CDM models complete.

**Profile models** (in `dbt_project/models/profiling/`):
- `profile_fact_orders.sql` — null rates, distinct counts, min/max/avg for fact_orders
- `profile_dim_customers.sql` — customer completeness, loyalty tier distribution
- `profile_fact_inventory.sql` — stock health, zero-stock %, negative availability
- `profile_fact_returns.sql` — return rate vs orders, refund stats

**Custom macro** (`dbt_project/macros/alert_high_null_rate.sql`): Generic null rate threshold test — alerts when null% exceeds configurable threshold.

**Statistical tests** (`dbt_expectations`): Column range checks, mean assertions, regex validation, FK tests — all in `dbt_project/models/cdm/schema.yml`.

**Airflow DAG order**: `dbt_run_cdm → dbt_run_profiling → dbt_test`

## Environment Variables

Key vars from `.env` (see `.env.example` for template):

```
# PostgreSQL
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

# MinIO
MINIO_ROOT_USER, MINIO_ROOT_PASSWORD

# Trino
TRINO_HOST (default: trino), TRINO_PORT (default: 8080)

# Airflow
AIRFLOW_HOST (default: airflow-webserver)

# OpenMetadata
OM_HOST (default: openmetadata-server), OM_PORT (default: 8585)
OM_USERNAME (default: admin), OM_PASSWORD (default: admin)
```

## Version Management

All Docker service versions are pinned to the latest stable releases verified on Docker Hub (May 2026). When upgrading:
- **MinIO**: Community edition `latest` points to `RELEASE.2025-09-07T16-13-09Z` (last community release on Docker Hub; no newer community tag has been published). Pin this tag — do not use `latest`.
- **Airflow 3.x**: Now on `apache/airflow:3.2.1`. The `webserver` command was removed → use `api-server`. DAG parsing runs in a separate `dag-processor` process. FAB auth manager is opt-in via `AIRFLOW__CORE__AUTH_MANAGER`. Health endpoint moved to `/api/v2/version`.
- **OpenMetadata 1.6 → 1.12 jump**: Major upgrade — runs a long DB migration on `openmetadata-server-init`. The `om_airflow` database schema is migrated by the bundled ingestion image; expect first-boot delays. Re-run `make bootstrap-om` after upgrade. If migrations fail, restore from a Postgres dump.
- **PostgreSQL 18**: New major version. Airflow 3.2 + OM 1.12 officially support PG13–PG17; PG18 works in tests but is technically untested upstream. Roll back to `postgres:17-alpine` if either service fails its DB migration.
- **Apache Hive 4.2.0**: Standalone metastore mode. The `hive-metastore-init` one-shot job runs `schematool -initSchema` against the `metastore` Postgres DB. Re-run only when wiping volumes.
- **OpenSearch 2.19.5**: OM 1.12+ supports OpenSearch natively via `SEARCH_TYPE=opensearch`. Heap pinned at `-Xms256m -Xmx512m`.
- **pandas**: Stay on 2.x (currently 2.2.3). pandas 3.0 has breaking changes.
- **Vite**: Stay on 5.x (currently 5.4.11). Vite 8.x uses Rolldown (experimental).
- **dbt**: `dbt-core==1.9.4`, `dbt-trino==1.9.2` — update together.
- **Node 22 LTS**: Active LTS until Oct 2025; maintenance LTS until Apr 2027.
- **Python 3.13**: Used by the API image. Stable, supported until Oct 2029.

## Development Notes

- **Minimum RAM:** 16 GB for all 13 Docker services
- **dbt project name:** `datalens_cdm`
- **dbt target:** Trino (host: trino:8080, user: admin)
- **Iceberg tables:** Incremental materialized, stored on MinIO
- **Airflow DAGs:** `dbt_to_om_dag`, `om_profiling_dag`, `wayfair_mock_dag`
- **OpenMetadata auth:** Base64-encoded password in login POST, JWT bearer thereafter
- **Frontend API proxy:** `VITE_API_BASE_URL` env var (default: http://localhost:8000)
- **node_modules:** Anonymous Docker volume for glibc isolation

## Scripts

`scripts/bootstrap_om_tokens.sh` — Fetches a JWT token from OpenMetadata and injects it into all ingestion config YAMLs. Run after OpenMetadata is healthy:

```bash
export OM_PASSWORD=<your-om-password>
make bootstrap-om
```

## OpenMetadata Ingestion Configs

```
openmetadata/ingestion/
├── postgres_service.yml   # Register PostgreSQL as OM service
├── trino_service.yml      # Register Trino as OM service
├── dbt_ingestion.yml      # Ingest dbt artifacts (manifest, catalog, run_results)
└── profiler_trino.yml     # Profiling job config
```

## Modified Files (feature_add branch)

### Security
- `api/services/trino_client.py` — SQL injection fix: `_quote_id()` on all identifiers
- `api/services/om_client.py` — hardcoded credentials removed, `OM_PASSWORD` required env var
- `api/services/airflow_client.py` — `AIRFLOW_ADMIN_PASSWORD` required env var

### Performance
- `api/services/om_client.py` — singleton factory `get_om_client()`, persistent httpx.AsyncClient, token expiry tracking
- `api/routers/sources.py` — 60s TTL cache for table counts (eliminates N+1)
- `api/routers/sources.py`, `cdm.py`, `dq.py` — `limit`/`offset` pagination on list endpoints
- `api/routers/_pagination.py` — new reusable pagination dependency

### Architecture
- `api/main.py` — structured JSON logging, request ID middleware, `/api/v1/` route versioning
- `frontend/vite.config.ts` — proxy updated to `/api/v1`
- `frontend/src/lib/api.ts` — baseURL updated to `/api/v1`

### dbt Profiling (replaces ydata-profiling)
- `dbt_project/models/profiling/` — 4 new profile models
- `dbt_project/models/cdm/schema.yml` — dbt_expectations statistical tests, FK tests, composite unique test
- `dbt_project/macros/alert_high_null_rate.sql` — new generic null rate macro
- `dbt_project/macros/assert_positive_amount.sql` — deleted (dead code)
- `dbt_project/dbt_project.yml` — profiling layer config added
- `dbt_project/packages.yml` — version constraints updated
- `airflow/dags/dbt_to_om_dag.py` — `dbt_run_profiling` step added, dbt test failures propagated, dagrun_timeout fixed

### Deleted (ydata-profiling removal)
- `api/routers/assessment.py` — deleted
- `api/services/assessment_service.py` — deleted

### Infrastructure
- `docker-compose.yml` — all versions pinned/upgraded, resource limits, healthchecks
- `airflow/Dockerfile` — Airflow 2.10.5, dbt-core 1.9.4, dbt-trino 1.9.2
- `api/requirements.txt` — all deps upgraded, ydata-profiling removed
- `.env.example` — required env vars marked

### New
- `scripts/bootstrap_om_tokens.sh` — OM JWT token bootstrap script
- `Makefile` — `bootstrap-om` target
- `docs/PRODUCT-OVERVIEW.md` — non-technical product overview
- `docs/DEVELOPER-GUIDE.md` — developer onboarding guide
- `docs/DATA-QUALITY.md` — data quality reference

## Common Pitfalls

- OpenMetadata takes ~2 min to start; health check may fail initially
- Airflow needs `airflow-init` one-shot service to complete before api-server/scheduler/dag-processor
- **Airflow 3.x**: `airflow webserver` command is REMOVED. Use `airflow api-server` (compose uses the `airflow-apiserver` service). Health endpoint moved to `/api/v2/version`.
- **Airflow 3.x DAG parsing** runs in a separate `dag-processor` process — compose has a dedicated `airflow-dag-processor` service.
- **Hive metastore**: use `apache/hive:4.0.1` standalone metastore. Requires one-shot `schematool -initSchema` (the `hive-metastore-init` service in compose) before the main metastore starts. The `bitsondatadev/hive-metastore` image is abandonware and does NOT auto-initialize the schema (`MetaException: Version information not found in metastore.`).
- **Search backend**: now OpenSearch 2.18.0 (was Elasticsearch). OpenMetadata 1.6+ supports it via `SEARCH_TYPE=opensearch`. Cuts ~500MB heap.
- dbt profiles.yml points to internal Docker hostname `trino:8080`, not localhost
- MinIO must initialize before Iceberg catalog works in Trino
- `OM_USERNAME` must be `admin@open-metadata.org` — confirmed from `user_entity` table. OM login POST `/api/v1/users/login` requires email field (base64-encoded password)
- `AIRFLOW_PORT` inside Docker network is `8080` (not `8082` which is host-only mapping)
- `openmetadata-ingestion` must run both `airflow webserver` AND `airflow scheduler` — scheduler alone doesn't expose HTTP port 8080 that OM server needs for `PIPELINE_SERVICE_CLIENT_ENDPOINT`. NOTE: this image bundles its own Airflow 2.x — webserver command still works there.
- Env var names: code reads `OM_USERNAME`/`OM_PASSWORD`; `.env` must use these exact names (not `OM_ADMIN_USER`/`OM_ADMIN_PASSWORD`)
- `OM_PASSWORD` env var is now REQUIRED — no default. App fails to start without it.
- `AIRFLOW_ADMIN_PASSWORD` env var is now REQUIRED — no default.
- API routes are now versioned: `/api/v1/sources`, `/api/v1/dq`, etc. `/health` stays unversioned.
- MinIO `latest` tag is dead (archived Apr 2026) — use pinned tag only.
- ydata-profiling is removed. Assessment endpoints no longer exist. Use dbt profiling models.
- dbt test failures now FAIL the Airflow DAG (no longer silently swallowed).
- Trino catalog properties now reference MinIO creds via `${ENV:MINIO_ROOT_USER}` / `${ENV:MINIO_ROOT_PASSWORD}`; compose injects these vars into the trino service. No more hardcoded secrets in `infra/trino/catalog/*.properties`.
- Every service has `deploy.resources.limits` (memory + cpus) — prevents one container's OOM from cascading. Estimated total cap: ~14GB across the stack.
