# Retail dbt Test Generation POC

Standalone POC inside the datalens project. Demonstrates auto-generating dbt tests from OpenMetadata schema using a local LLM (Ollama).

## Stack

- **PostgreSQL 17** — retail data (~140K rows, 14 tables)
- **OpenMetadata 1.5.x** — schema catalog and metadata extraction
- **Ollama** (`qwen2.5-coder:3b`) — local LLM for dbt test generation
- **dbt-postgres** — direct PostgreSQL profile
- **Jupyter** — pipeline orchestration and results preview

## Quick Start

```bash
# 1. Start services
docker compose up -d

# 2. Install Python deps
pip install -r requirements.txt

# 3. Seed retail data
python db/seed.py

# 4. Run the pipeline notebook
make notebook
# or: jupyter notebook notebooks/pipeline.ipynb

# 5. (Optional) View dbt docs
make dbt-docs
# → http://localhost:8082
```

## Services

| Service | URL |
|---------|-----|
| PostgreSQL | localhost:5435 |
| OpenMetadata | http://localhost:8588 |
| Elasticsearch | http://localhost:9202 |
| Ollama | http://localhost:11434 |
| dbt docs | http://localhost:8082 |

## Validation

```bash
make validate
```
