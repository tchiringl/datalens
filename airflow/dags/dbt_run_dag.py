"""
dbt_run_dag.py
--------------
Airflow DAG that:
  1. Installs dbt dependencies
  2. Runs dbt for staging models
  3. Runs dbt for CDM models
  4. Runs dbt profiling models (column-level statistics)
  5. Executes all dbt tests (with --store-failures)
  6. Generates dbt docs (produces manifest.json, catalog.json, run_results.json)
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DBT_PROJECT_DIR = "/opt/airflow/dbt_project"

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
default_args = {
    "owner": "datalens",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="dbt_run_dag",
    default_args=default_args,
    description="Run dbt CDM build, profiling, and data quality tests",
    schedule=None,          # API-triggered only; set a cron here if needed
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["datalens", "dbt", "cdm"],
    max_active_runs=3,
    dagrun_timeout=timedelta(hours=4),
    doc_md="""
## dbt CDM Build & Test DAG

**Purpose:** Build the CDM (staging → dimensions + facts), generate profiling
statistics, run all data quality tests, and produce dbt documentation artifacts.

**Task order:**
```
wait_for_trino → dbt_deps → dbt_run_staging → dbt_run_cdm → dbt_run_profiling
              → dbt_test → dbt_docs_generate
```

**Trigger:** Triggered via Airflow API. Set `schedule_interval` to a cron string
to also run on a schedule (e.g., daily).

**Output artifacts:** Produces manifest.json, catalog.json, run_results.json in
dbt_project/target/. Test failures (if any) are stored in a dbt failures table
for inspection.
""",
) as dag:
    # -----------------------------------------------------------------------
    # Preflight – wait until Trino is query-ready
    # -----------------------------------------------------------------------
    wait_for_trino = BashOperator(
        task_id="wait_for_trino",
        bash_command=(
            "for i in $(seq 1 60); do "
            "curl -sf http://trino:8080/v1/info | grep -q '\"starting\":false' && exit 0; "
            "sleep 2; "
            "done; "
            "echo 'Trino not ready in time'; exit 1"
        ),
        doc_md="Wait until Trino reports starting=false before launching dbt tasks.",
    )

    # -----------------------------------------------------------------------
    # Step 1 – Install / update dbt packages (packages.yml)
    # -----------------------------------------------------------------------
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt deps --profiles-dir {DBT_PROJECT_DIR}",
        doc_md="Install or update dbt packages defined in packages.yml.",
    )

    # -----------------------------------------------------------------------
    # Step 2 – Build staging layer
    # -----------------------------------------------------------------------
    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt run --select staging --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        doc_md="Build all models in the `staging` layer.",
    )

    # -----------------------------------------------------------------------
    # Step 3 – Build CDM (Canonical Data Model) layer
    # -----------------------------------------------------------------------
    dbt_run_cdm = BashOperator(
        task_id="dbt_run_cdm",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt run --select cdm --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        doc_md="Build all models in the `cdm` layer (facts + dimensions).",
    )

    # -----------------------------------------------------------------------
    # Step 4 – Run profiling models (column-level stats for each CDM table)
    # -----------------------------------------------------------------------
    dbt_run_profiling = BashOperator(
        task_id="dbt_run_profiling",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt run --select profiling --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        execution_timeout=timedelta(minutes=30),
        doc_md="Build profiling models — null rates, distinct counts, distribution stats per CDM table.",
    )

    # -----------------------------------------------------------------------
    # Step 5 – Run all tests, persist failures to a table for inspection
    # -----------------------------------------------------------------------
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt test --store-failures --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        doc_md="Execute all dbt schema / data tests. Failures are stored in a test failures table.",
    )

    # -----------------------------------------------------------------------
    # Step 6 – Generate docs (produces manifest.json + catalog.json)
    # -----------------------------------------------------------------------
    dbt_docs_generate = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt docs generate --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        doc_md="Generate dbt documentation artifacts: manifest.json, catalog.json, run_results.json.",
    )

    # -----------------------------------------------------------------------
    # Pipeline dependency chain
    # -----------------------------------------------------------------------
    (
        wait_for_trino
        >> dbt_deps
        >> dbt_run_staging
        >> dbt_run_cdm
        >> dbt_run_profiling
        >> dbt_test
        >> dbt_docs_generate
    )
