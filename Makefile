# =============================================================================
# Data Lens Retail AI POC — Makefile
# =============================================================================
# Usage:  make <target>
# Run `make help` to see all available targets.
# =============================================================================

.PHONY: help up down reset logs trino-cli dbt-run dbt-test validate status bootstrap-om

## Show this help message
help:
	@echo ""
	@echo "Data Lens Retail AI POC — available make targets"
	@echo "================================================"
	@grep -E '^## ' Makefile | sed 's/## /  /'
	@echo ""

## Start all services in detached mode
up:
	docker compose up -d

## Stop all running containers (preserves volumes)
down:
	docker compose down

## WARNING: destroys all data — removes containers AND named volumes
reset:
	@echo "WARNING: This will permanently delete all data volumes."
	@echo "Press Ctrl-C within 5 seconds to abort..."
	@sleep 5
	docker compose down -v

## Stream logs from all services (Ctrl-C to exit)
logs:
	docker compose logs -f

## Open an interactive Trino CLI session
trino-cli:
	docker compose exec trino trino

## Run dbt models inside the API container
dbt-run:
	docker compose exec api bash -c "cd /dbt && dbt run"

## Run dbt tests inside the API container
dbt-test:
	docker compose exec api bash -c "cd /dbt && dbt test"

## Check health endpoints for all services
validate:
	@echo ""
	@echo "Validating Data Lens service health endpoints..."
	@echo "==============================================="
	@echo ""
	@_check() { \
	  label=$$1; url=$$2; \
	  if curl -sf --max-time 5 "$$url" > /dev/null 2>&1; then \
	    printf "  [OK]  %-30s %s\n" "$$label" "$$url"; \
	  else \
	    printf "  [FAIL] %-30s %s\n" "$$label" "$$url"; \
	  fi; \
	}; \
	_check "PostgreSQL (pg_isready)" "N/A — use: docker compose exec postgres pg_isready"; \
	_check "MinIO S3 API"            "http://localhost:9000/minio/health/live"; \
	_check "MinIO Console"           "http://localhost:9001"; \
	_check "Trino UI"                "http://localhost:8080/v1/info"; \
	_check "Airflow Webserver"       "http://localhost:8082/health"; \
	_check "Elasticsearch"           "http://localhost:9200/_cluster/health"; \
	_check "OpenMetadata Server"     "http://localhost:8585"; \
	_check "API /health"             "http://localhost:8000/health"; \
	_check "Frontend"                "http://localhost:3000"
	@echo ""
	@echo "PostgreSQL status:"
	@docker compose exec postgres pg_isready -U $${POSTGRES_USER:-datalens} || true
	@echo ""

## Show the current status of all containers
status:
	docker compose ps

## Bootstrap OpenMetadata JWT tokens into ingestion configs (run after make up)
bootstrap-om:
	@bash scripts/bootstrap_om_tokens.sh


## Start services in stages to prevent resource crashes
up-staged:
	@echo "1. Starting base infrastructure..."
	docker compose up -d postgres minio elasticsearch
	@echo "Waiting 20s for databases to initialize..."
	@sleep 20
	
	@echo "2. Starting initialization jobs and metastores..."
	docker compose up -d minio-init hive-metastore airflow-init openmetadata-server-init openmetadata-ingestion-init
	@echo "Waiting 30s for migrations to run..."
	@sleep 30
	
	@echo "3. Starting compute engines and web apps..."
	docker compose up -d trino airflow-webserver airflow-scheduler openmetadata-server openmetadata-ingestion api frontend
	@echo "Stack is coming up! Run 'make validate' in a few moments to check health."
