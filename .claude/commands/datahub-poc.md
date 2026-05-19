# /datalens-poc

Build, scaffold, or extend the Data Lens Retail AI Data Lens POC. This skill covers the full stack: infrastructure, backend pipelines, and the modern React frontend GUI.

## Usage

```
/datalens-poc                        # Show menu of available actions
/datalens-poc scaffold               # Scaffold the full project structure
/datalens-poc infra                  # Generate docker-compose + configs
/datalens-poc seed                   # Generate PostgreSQL seed data + schema
/datalens-poc dbt                    # Scaffold dbt project (models, tests, profiles)
/datalens-poc airflow                # Generate Airflow DAGs
/datalens-poc openmetadata           # Generate OpenMetadata ingestion configs
/datalens-poc frontend               # Scaffold the React frontend GUI
/datalens-poc frontend <component>   # Build a specific frontend component
/datalens-poc validate               # Print the full validation checklist
/datalens-poc status                 # Check which POC components exist on disk
```

---

## Platform Context

**Architecture:** Lakehouse + Trino-first federated query
**Deployment:** Docker Compose (local POC), Kubernetes-ready later
**Consumers:** AI/ML engines via Common Data Model (CDM)

### Tech Stack

| Role | Tool |
|---|---|
| Storage | MinIO (S3) + Apache Iceberg |
| Query Engine | Trino |
| Transformation | dbt (dbt-trino adapter) |
| Orchestration | Apache Airflow |
| Governance | OpenMetadata |
| Source DB | PostgreSQL |
| Profiling | YData Profiling |
| API Ingestion | Python custom pipeline |
| Frontend | React + TypeScript + Tailwind CSS + shadcn/ui |
| Frontend API | FastAPI (Python) |

---

## Action: scaffold

Create the full project directory tree with placeholder files:

```
datalens-poc/
├── docker-compose.yml
├── .env.example
├── README.md
├── infra/
│   └── trino/
│       └── catalog/
│           ├── postgres.properties
│           └── iceberg.properties
├── db/
│   └── init.sql
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/
│   │   └── cdm/
│   └── tests/
├── airflow/
│   └── dags/
├── openmetadata/
│   └── ingestion/
├── ingestion/
│   └── wayfair_mock.py
├── profiling/
│   └── run_profile.py
├── api/
│   ├── main.py
│   ├── routers/
│   └── requirements.txt
└── frontend/
    ├── package.json
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   ├── pages/
    │   ├── hooks/
    │   └── lib/
    └── public/
```

---

## Action: infra

Generate the following files in full (no truncation):

### `docker-compose.yml`
Include these services with health checks:
- `postgres` — source DB, port 5432, init from `./db/init.sql`
- `minio` — S3-compatible store, ports 9000/9001, with bucket auto-creation
- `minio-init` — one-shot container to create the `warehouse` bucket
- `trino` — port 8080, mounts `./infra/trino/catalog/`
- `airflow-init` — DB init + admin user creation
- `airflow-webserver` — port 8082
- `airflow-scheduler`
- `openmetadata-server` — port 8585
- `openmetadata-ingestion`
- `elasticsearch` — required by OpenMetadata
- `api` — FastAPI backend, port 8000, mounts `./api/`
- `frontend` — React dev server, port 3000, mounts `./frontend/`

All services share a `datalens-net` bridge network.
Use `.env` for all credentials.

### `.env.example`
```
POSTGRES_USER=datalens
POSTGRES_PASSWORD=datalens123
POSTGRES_DB=retail
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
AIRFLOW_UID=50000
AIRFLOW__CORE__FERNET_KEY=<generate>
OPENMETADATA_HOST=openmetadata-server
TRINO_HOST=trino
API_HOST=api
```

### `infra/trino/catalog/postgres.properties`
```
connector.name=postgresql
connection-url=jdbc:postgresql://postgres:5432/retail
connection-user=${POSTGRES_USER}
connection-password=${POSTGRES_PASSWORD}
```

### `infra/trino/catalog/iceberg.properties`
```
connector.name=iceberg
iceberg.catalog.type=hive_metastore
hive.metastore.uri=thrift://hive-metastore:9083
hive.s3.endpoint=http://minio:9000
hive.s3.aws-access-key=${MINIO_ROOT_USER}
hive.s3.aws-secret-key=${MINIO_ROOT_PASSWORD}
hive.s3.path-style-access=true
```

---

## Action: seed

Generate `db/init.sql` with:

### Schema
```sql
-- customers, products, stores, orders, order_details
-- Include: primary keys, foreign keys, timestamps
-- Partitioning-friendly: include created_at DATE columns
```

### Data requirements
- 200 customers (mix of nulls in email for DQ testing)
- 50 products (mix of categories)
- 10 stores
- 500 orders (some with duplicate order_ids for DQ testing)
- 1000 order_details
- Use `generate_series` or explicit INSERTs

---

## Action: dbt

Generate a complete dbt project with dbt-trino adapter:

### `dbt_project.yml`
- project name: `datalens_cdm`
- models materialized as `incremental` for cdm layer, `view` for staging

### `profiles.yml`
- target: trino
- host: trino, port: 8080, user: admin
- http_scheme: http

### Staging models (`models/staging/`)
- `stg_customers.sql` — clean nulls, cast types
- `stg_products.sql`
- `stg_stores.sql`
- `stg_orders.sql` — deduplicate on order_id
- `stg_order_details.sql`

### CDM models (`models/cdm/`)
- `dim_customers.sql` — SCD Type 1, partition by created_date
- `dim_products.sql`
- `dim_stores.sql`
- `fact_orders.sql` — joins order + order_details + store
- Write to Iceberg on MinIO

### `models/cdm/schema.yml`
Tests for every CDM model:
- `not_null` on all PK columns
- `unique` on all PK columns
- `relationships` for all FK columns
- Custom test: `assert_positive_order_amount`

---

## Action: airflow

### `airflow/dags/dbt_to_om_dag.py`
```python
# DAG: dbt_to_om_dag
# Schedule: None (API-triggered only)
# Tasks:
#   1. dbt_run        — BashOperator: dbt run --project-dir ...
#   2. dbt_test       — BashOperator: dbt test (runs after dbt_run)
#   3. om_ingest_dbt  — PythonOperator: POST to OM ingestion API
#   4. om_ingest_trino — PythonOperator: trigger Trino metadata ingestion
# Use: logical_date must be unique per run
# Include: retry logic (3 retries, 5min delay)
```

### `airflow/dags/wayfair_mock_dag.py`
```python
# DAG: wayfair_mock_ingestion
# Schedule: @daily
# Tasks:
#   1. extract  — PythonOperator: call mock REST API (httpbin or local mock)
#   2. validate — PythonOperator: basic schema checks
#   3. load     — PythonOperator: write to Iceberg raw layer via Trino INSERT
```

---

## Action: openmetadata

### `openmetadata/ingestion/trino_service.yml`
Register Trino as a DatabaseService and trigger metadata ingestion.

### `openmetadata/ingestion/postgres_service.yml`
Register PostgreSQL as a DatabaseService.

### `openmetadata/ingestion/dbt_ingestion.yml`
Ingest dbt artifacts:
- manifest.json path
- catalog.json path
- run_results.json path
- Map to existing Trino service

---

## Action: frontend

Build a modern React + TypeScript + Tailwind CSS + shadcn/ui frontend.

### Design System
- Dark sidebar navigation
- Light main content area
- Color palette: slate-900 sidebar, white content, blue-600 accent
- Font: Inter
- Cards with subtle shadows and rounded-xl corners
- Status indicators: green (healthy), yellow (warning), red (failed)

### Pages & Components

#### 1. Dashboard (`/`)
- KPI cards row: Total Sources, CDM Models Built, DQ Tests Passing, Pipeline Runs Today
- Pipeline health bar (Airflow DAG statuses)
- Recent activity feed (last 10 events)
- Quick-action buttons: Trigger Pipeline, Add Source, View Lineage

#### 2. Sources (`/sources`)
- Table of registered data sources (name, type, status, last synced)
- "Add Source" modal with form: name, type (postgres/redshift/bigquery/api), credentials
- Per-source: connection status badge, "Sync Now" button, "View in OpenMetadata" link
- Source detail drawer: shows tables, row counts, last profiling date

#### 3. Pipelines (`/pipelines`)
- DAG cards with: name, schedule, last run status, duration, next run
- Trigger DAG button (calls Airflow API via FastAPI backend)
- Run history table per DAG: date, status, duration
- Live status polling (queued → running → success/failed) via React Query

#### 4. CDM Explorer (`/cdm`)
- Tree view: CDM entity → tables → columns
- Column detail panel: type, nullable, DQ test status
- dbt model lineage mini-graph (source → staging → CDM)

#### 5. Data Quality (`/data-quality`)
- Summary ring charts: total tests, passing, failing
- Test results table: model, column, test type, status, last run
- Filter by: status, model, test type
- Failing tests highlighted in red with expandable error detail

#### 6. Governance (`/governance`)
- Embed OpenMetadata iframe OR replicate key views:
  - Asset catalog table
  - Lineage graph (D3 or ReactFlow)
  - Ownership assignments

### Frontend API (`api/`)

FastAPI backend that the React app talks to:

```
GET  /api/sources              — list all registered sources
POST /api/sources              — register new source (triggers OM + Trino catalog)
GET  /api/pipelines            — list DAGs from Airflow
POST /api/pipelines/{dag_id}/trigger  — trigger a DAG run
GET  /api/pipelines/{dag_id}/runs     — get run history
GET  /api/dq/results           — get dbt test results from OM
GET  /api/cdm/models           — list CDM models and their columns
GET  /api/health               — overall platform health check
```

Use `httpx` async client to proxy to Airflow, OpenMetadata, and Trino REST APIs.

---

## Action: validate

Print this checklist:

```
Data Lens POC Validation Checklist
=================================

Infrastructure
[ ] All Docker services start: docker compose up -d
[ ] All services healthy: docker compose ps

Trino
[ ] Postgres catalog queryable: SELECT * FROM postgres.public.customers LIMIT 5
[ ] Iceberg catalog queryable: SHOW SCHEMAS FROM iceberg

dbt
[ ] dbt debug passes
[ ] dbt run completes (0 errors)
[ ] dbt test results include expected failures on seeded DQ issues

Airflow
[ ] dbt_to_om_dag visible in Airflow UI (localhost:8082)
[ ] DAG triggerable via API: POST /api/v1/dags/dbt_to_om_dag/dagRuns
[ ] wayfair_mock_dag runs and writes to Iceberg

OpenMetadata
[ ] Trino service registered and metadata ingested (localhost:8585)
[ ] dbt lineage visible: postgres → staging → CDM
[ ] dbt test results shown in Data Quality tab

Frontend
[ ] Dashboard loads at localhost:3000
[ ] Sources page lists seeded sources
[ ] Pipeline trigger works end-to-end
[ ] DQ test results displayed correctly

Profiling
[ ] YData report generated: python profiling/run_profile.py
```

---

## Action: status

Check which files and directories exist:

Scan the following paths and report present (✓) or missing (✗):
- `docker-compose.yml`
- `.env.example`
- `db/init.sql`
- `infra/trino/catalog/postgres.properties`
- `infra/trino/catalog/iceberg.properties`
- `dbt_project/dbt_project.yml`
- `dbt_project/profiles.yml`
- `dbt_project/models/staging/`
- `dbt_project/models/cdm/`
- `airflow/dags/dbt_to_om_dag.py`
- `airflow/dags/wayfair_mock_dag.py`
- `openmetadata/ingestion/`
- `ingestion/wayfair_mock.py`
- `profiling/run_profile.py`
- `api/main.py`
- `frontend/package.json`
- `frontend/src/App.tsx`

---

## Engineering Standards (apply to all generated code)

- All credentials via environment variables — never hardcoded
- All Airflow DAGs must be idempotent
- dbt CDM models use `incremental` materialization with `unique_key`
- Iceberg tables partitioned by date column where applicable
- OpenMetadata profiling decoupled from source onboarding
- FastAPI routes use async/await with httpx
- React components use TypeScript strict mode
- No Kubernetes manifests in this phase
- Flag assumptions as `# ASSUMPTION: ...`
- Flag future work as `# FUTURE: ...`
