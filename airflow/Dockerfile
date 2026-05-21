# =============================================================================
# DataLens — Airflow 3.x image
# Base: official apache/airflow 3.2.1 (latest stable 3.x per Docker Hub).
# Adds: fab + standard providers, dbt-core/dbt-trino, trino driver.
# =============================================================================
FROM apache/airflow:3.2.1

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

USER airflow

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Provider packages required for Airflow 3.x:
#   - FAB: restores `airflow users create` CLI and UI auth.
#   - standard: BashOperator, PythonOperator, etc.
#   - trino: TrinoHook/Operator for DAG tasks.
RUN pip install --no-cache-dir \
        "apache-airflow-providers-fab>=2.0" \
        "apache-airflow-providers-standard>=1.0" \
        "apache-airflow-providers-trino>=6.0"

# Extra Python deps used by DAG code (DB-API client, etc).
COPY requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt

# dbt-core 1.9.x has an importlib-metadata conflict with Airflow 3.x core.
# Pin importlib-metadata to a version satisfying both, then install dbt.
RUN pip install --no-cache-dir "importlib-metadata>=7.0,<8" \
 && pip install --no-cache-dir \
        dbt-core==1.9.4 \
        dbt-trino==1.9.2

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/v2/version || exit 1
