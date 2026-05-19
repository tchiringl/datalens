# DataHub Retail AI POC

## Overview

This repository contains the complete infrastructure layer for a Retail AI proof-of-concept built on an open-source modern data stack. It federates data across a PostgreSQL operational database, an Iceberg/MinIO data lake, and optional cloud warehouses (Redshift, BigQuery) through a Trino query engine, orchestrates ingestion pipelines with Apache Airflow, governs metadata with OpenMetadata, and exposes AI-powered retail analytics through a FastAPI backend and React/Vite frontend. The entire stack runs locally in Docker Compose, making it straightforward to reproduce, demo, and extend.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DataHub Retail AI POC                          │
│                         (Docker Compose Stack)                          │
└─────────────────────────────────────────────────────────────────────────┘

  Browser / Client
       │
       ▼
  ┌─────────────┐      HTTP/REST      ┌──────────────────────┐
  │  Frontend   │ ──────────────────► │   API (FastAPI)      │
  │  (React/    │                     │   :8000              │
  │   Vite)     │                     └─────────┬────────────┘
  │  :3000      │                               │ JDBC / SQLAlchemy
  └─────────────┘                               │
                                    ┌───────────┴────────────┐
                                    │      Trino :8080        │
                                    │  (Federated SQL Engine) │
                                    └──┬──────┬──────┬───────┘
                                       │      │      │
                      ┌────────────────┘      │      └──────────────────┐
                      ▼                       ▼                         ▼
             ┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐
             │  PostgreSQL  │      │  Iceberg Catalog │      │ Cloud Warehouses │
             │  :5432       │      │  (Hive Metastore │      │ (Redshift /      │
             │  - retail DB │      │   :9083)         │      │  BigQuery)       │
             │  - airflow   │      │       │          │      │  [FUTURE]        │
             │  - om schema │      └───────┼──────────┘      └──────────────────┘
             └──────────────┘              │ thrift
                    ▲                      ▼
                    │             ┌──────────────────┐
                    │             │   MinIO :9000    │
                    │             │  (S3-compatible) │
                    │             │  warehouse/      │
                    │             │  raw/            │
                    │             └──────────────────┘
                    │
       ┌────────────┴───────────────────────────────────────┐
       │               Support Services                      │
       │                                                      │
       │  ┌───────────────────┐   ┌────────────────────────┐ │
       │  │ Airflow :8082     │   │ OpenMetadata :8585     │ │
       │  │ - Webserver       │   │ - Metadata Catalog     │ │
       │  │ - Scheduler       │   │ - Lineage & Discovery  │ │
       │  │ - Ingestion DAGs  │   │ (backed by ES :9200)   │ │
       │  └───────────────────┘   └────────────────────────┘ │
       └────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker Desktop | 4.x+ | Enable Docker Compose V2 in settings |
| RAM allocated to Docker | 16 GB minimum | 20 GB recommended for all services |
| Disk space | 20 GB free | For images, volumes, and data |
| Available ports | See table below | No other services on these ports |

### Required Ports

| Port | Service |
|---|---|
| 3000 | Frontend |
| 5432 | PostgreSQL |
| 8000 | API |
| 8080 | Trino UI |
| 8082 | Airflow Webserver |
| 8585 | OpenMetadata |
| 9000 | MinIO S3 API |
| 9001 | MinIO Console |
| 9083 | Hive Metastore (internal) |
| 9200 | Elasticsearch |

---

## Quick Start

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-org/datahub-retail-poc.git
cd datahub-retail-poc
```

### Step 2 — Configure environment variables

```bash
cp .env.example .env
# Open .env in your editor and replace placeholder values:
#   - POSTGRES_PASSWORD (use a strong password)
#   - SECRET_KEY  (generate with: python -c "import secrets; print(secrets.token_hex(32))")
#   - AIRFLOW__CORE__FERNET_KEY  (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### Step 3 — Start all services

```bash
make up
```

Docker Compose will pull all images and start 13 services. Initial startup takes 3–5 minutes on a fast internet connection. Watch progress with:

```bash
make logs
```

### Step 4 — Validate all service health endpoints

```bash
make validate
```

All entries should report `[OK]`. If a service shows `[FAIL]`, wait 30 seconds and retry — some services (Airflow, OpenMetadata) take longer to initialise.

### Step 5 — Open the service URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Documentation (Swagger) | http://localhost:8000/docs |
| Trino UI | http://localhost:8080/ui |
| Airflow | http://localhost:8082 |
| OpenMetadata | http://localhost:8585 |
| MinIO Console | http://localhost:9001 |

---

## Service URLs Reference

| Service | URL | Default Credentials |
|---|---|---|
| Frontend | http://localhost:3000 | — |
| API (Swagger UI) | http://localhost:8000/docs | — |
| API (ReDoc) | http://localhost:8000/redoc | — |
| Trino Web UI | http://localhost:8080/ui | user: `admin`, no password |
| Airflow Webserver | http://localhost:8082 | admin / admin123 |
| OpenMetadata | http://localhost:8585 | admin / admin |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin123 |
| Elasticsearch | http://localhost:9200 | no auth (security disabled) |
| PostgreSQL | localhost:5432 | datahub / datahub123 |

---

## Component Descriptions

### PostgreSQL 15
Central relational database serving three roles: the retail operational database (`retail`), the Airflow metadata store (`airflow`), and the OpenMetadata schema (`openmetadata`). Initialised from `./db/init.sql` on first start.

### MinIO
S3-compatible object storage running locally. Two buckets are created automatically:
- **warehouse** — Parquet files for Iceberg-managed tables.
- **raw** — Landing zone for CSV/JSON files ingested by Airflow DAGs.

### Hive Metastore
Catalog service for Apache Iceberg. Stores table schemas, partition metadata, and S3 file paths in PostgreSQL. Trino connects to it over the Thrift protocol on port 9083.

### Trino 426
Distributed SQL query engine that federates queries across all registered catalogs:
- **postgres** — direct access to the retail operational schema.
- **iceberg** — Parquet files in MinIO via Hive Metastore.
- **redshift** — Amazon Redshift (placeholder, activate when credentials available).
- **bigquery** — Google BigQuery (placeholder, activate when credentials available).

### Apache Airflow 2.9.1
Workflow orchestration for ETL/ELT pipelines. Runs with the LocalExecutor backed by PostgreSQL. DAGs are stored in `./dags/` (mount this directory into the scheduler and webserver containers as needed).

### Elasticsearch 8.11.0
Full-text search and analytics engine used exclusively as the OpenMetadata index backend. Security is disabled for the local POC. Do not expose port 9200 externally.

### OpenMetadata 1.3.1
Open-source data catalog providing:
- Automated metadata discovery and ingestion.
- Column-level data lineage.
- Data quality assertions.
- Searchable data asset catalogue.

The ingestion container runs Airflow internally to schedule metadata crawls.

### API (FastAPI)
Python FastAPI application built from `./api/`. Exposes:
- `/health` — liveness probe.
- `/docs` — Swagger UI.
- Retail AI endpoints (demand forecasting, recommendation, anomaly detection).
Queries Trino via `trino-python-client` for analytical workloads and PostgreSQL via SQLAlchemy for transactional reads/writes.

### Frontend (React/Vite)
Single-page application built from `./frontend/`. Communicates with the API via `VITE_API_BASE_URL`. Runs in development mode (`vite dev`) inside Docker for the POC; swap the Dockerfile to a multi-stage Nginx build for production.

---

## Makefile Targets Reference

| Target | Description |
|---|---|
| `make up` | Start all services in detached mode |
| `make down` | Stop all containers, preserve volumes |
| `make reset` | Stop containers AND delete all data volumes (irreversible) |
| `make logs` | Stream live logs from all containers |
| `make status` | Show container status and port bindings |
| `make trino-cli` | Open an interactive Trino CLI session |
| `make dbt-run` | Execute `dbt run` inside the API container |
| `make dbt-test` | Execute `dbt test` inside the API container |
| `make validate` | Curl each service health endpoint and report pass/fail |

---

## Validation Checklist

Run `make validate` and verify the following manually:

- [ ] PostgreSQL: `docker compose exec postgres pg_isready -U datahub` prints `accepting connections`
- [ ] MinIO: http://localhost:9001 loads the login page; buckets `warehouse` and `raw` are visible after login
- [ ] Trino: http://localhost:8080/v1/info returns JSON with `"starting":false`
- [ ] Trino catalogs: `make trino-cli` then `SHOW CATALOGS;` lists `iceberg`, `postgres`, `redshift`, `bigquery`
- [ ] Airflow: http://localhost:8082 redirects to the login page; login with admin / admin123 succeeds
- [ ] Elasticsearch: `curl http://localhost:9200/_cluster/health` returns `"status":"green"` or `"yellow"`
- [ ] OpenMetadata: http://localhost:8585 loads the login page; login with admin / admin succeeds
- [ ] API: `curl http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] API Swagger: http://localhost:8000/docs loads the interactive documentation
- [ ] Frontend: http://localhost:3000 loads the dashboard

---

## Known Limitations

1. **Single-node Trino** — The coordinator also acts as a worker (`node-scheduler.include-coordinator=true`). Suitable for the POC but not for production workloads requiring isolation.

2. **No TLS** — All services communicate over plain HTTP inside the Docker network. Do not expose any ports to the public internet without adding TLS termination (e.g., Nginx + Let's Encrypt or Traefik).

3. **Airflow LocalExecutor** — Only one task runs at a time per scheduler. For parallel pipeline execution in production, switch to the CeleryExecutor with a Redis broker.

4. **Hive Metastore image** — `bitsondatadev/hive-metastore:latest` is a community image. For production, build your own image from the official Apache Hive release to control versions and apply security patches.

5. **Static MinIO credentials** — The MinIO access key and secret are stored in `.env` and injected as environment variables. In production, use AWS IAM roles (if running on EC2/EKS) or a secrets manager (Vault, AWS Secrets Manager).

6. **OpenMetadata first-run time** — OpenMetadata may take 3–7 minutes to complete its database migration on first boot. If the login page shows an error, wait and retry.

7. **Frontend development mode** — The frontend Dockerfile is expected to run `vite dev`, which enables HMR but is not suitable for production. Replace with a multi-stage build (`vite build` + Nginx) before any external deployment.

8. **Redshift and BigQuery catalogs** — These catalog files contain placeholder credentials. Queries against these catalogs will fail until real credentials are supplied and the Trino container is restarted.

9. **No persistent Airflow DAG directory** — DAG files need to be mounted into both `airflow-webserver` and `airflow-scheduler`. Add the volume `./dags:/opt/airflow/dags` to both services in `docker-compose.yml` once the DAG directory exists.

10. **Resource contention** — Running all 13 services simultaneously requires at least 16 GB RAM allocated to Docker. On machines with less RAM, start only the services you need with `docker compose up -d postgres minio trino api`.
