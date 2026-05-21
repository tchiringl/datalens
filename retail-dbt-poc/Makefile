.PHONY: up down reset status logs seed notebook dbt-run dbt-test dbt-docs validate

PROJECT_DIR := $(shell pwd)
DBT_DIR := $(PROJECT_DIR)/dbt_project

up:
	docker compose up -d

down:
	docker compose down

reset:
	docker compose down -v

status:
	docker compose ps

logs:
	docker compose logs -f

seed:
	python db/seed.py

notebook:
	cd notebooks && jupyter notebook pipeline.ipynb

dbt-run:
	cd $(DBT_DIR) && dbt run --profiles-dir .

dbt-test:
	cd $(DBT_DIR) && dbt test --store-failures --profiles-dir .

dbt-docs:
	cd $(DBT_DIR) && dbt docs generate --profiles-dir . && dbt docs serve --port 8082 --profiles-dir .

validate:
	@echo "Checking PostgreSQL..."
	@docker compose exec postgres pg_isready -U retail -d retail && echo "PostgreSQL OK" || echo "PostgreSQL FAIL"
	@echo "Checking Ollama..."
	@curl -sf http://localhost:11434/api/tags > /dev/null && echo "Ollama OK" || echo "Ollama FAIL"
