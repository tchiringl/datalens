"""
dbt_to_om_dag.py
----------------
Airflow DAG that:
  1. Installs dbt dependencies
  2. Runs dbt for staging models
  3. Runs dbt for CDM models
  4. Executes all dbt tests (with --store-failures)
  5. Generates dbt docs (produces manifest.json, catalog.json, run_results.json)
  6. Pushes dbt artifacts to OpenMetadata via the ingestion pipeline API
  7. Triggers Trino metadata re-ingestion in OpenMetadata
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import requests
import os
import json
import logging
import time
import base64

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DBT_PROJECT_DIR = "/opt/airflow/dbt_project"
OM_HOST = os.getenv("OM_HOST", "openmetadata-server")
OM_PORT = os.getenv("OM_PORT", "8585")
OM_BASE_URL = f"http://{OM_HOST}:{OM_PORT}/api/v1"
OM_ADMIN_EMAIL = os.getenv("OM_ADMIN_EMAIL", "admin@open-metadata.org")
OM_ADMIN_PASSWORD = os.getenv("OM_ADMIN_PASSWORD", "admin")

# Names of ingestion pipelines that must already be registered in OM
DBT_PIPELINE_NAME = os.getenv("OM_DBT_PIPELINE_NAME", "dbt_ingestion_pipeline")
TRINO_PIPELINE_NAME = os.getenv("OM_TRINO_PIPELINE_NAME", "trino_metadata_pipeline")

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
# Helper functions
# ---------------------------------------------------------------------------

def get_om_token() -> str:
    """Authenticate against OpenMetadata and return a JWT access token."""
    url = f"{OM_BASE_URL}/users/login"
    encoded_password = base64.b64encode(OM_ADMIN_PASSWORD.encode("utf-8")).decode("utf-8")
    candidate_emails = [OM_ADMIN_EMAIL, "admin"]
    last_error = None

    for email in candidate_emails:
        payload = {"email": email, "password": encoded_password}
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            token = resp.json().get("accessToken")
            if token:
                logger.info("Successfully obtained OM access token for user=%s.", email)
                return token
            last_error = ValueError(f"No accessToken in OM login response: {resp.text}")
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"OpenMetadata login failed for configured users. Last error: {last_error}")


def _get_pipeline_id(pipeline_name: str, headers: dict) -> str | None:
    """Look up an ingestion pipeline by name and return its FQDN / id."""
    url = f"{OM_BASE_URL}/services/ingestionPipelines"
    params = {"fields": "id,name", "limit": 100}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    pipelines = resp.json().get("data", [])
    for pipeline in pipelines:
        if pipeline.get("name") == pipeline_name or pipeline.get("fullyQualifiedName", "").endswith(pipeline_name):
            return pipeline["id"]
    logger.warning(
        "Ingestion pipeline '%s' not found in OpenMetadata. Available=%s. Skipping OM trigger step.",
        pipeline_name,
        [p.get("name") for p in pipelines],
    )
    return None


def _trigger_pipeline(pipeline_id: str, headers: dict) -> None:
    """POST trigger to an ingestion pipeline by its UUID."""
    url = f"{OM_BASE_URL}/services/ingestionPipelines/trigger/{pipeline_id}"
    resp = requests.post(url, headers=headers, timeout=30)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Trigger failed for pipeline {pipeline_id}: "
            f"HTTP {resp.status_code} – {resp.text}"
        )
    logger.info("Pipeline %s triggered. Response: %s", pipeline_id, resp.status_code)


def _poll_pipeline_status(
    pipeline_id: str,
    headers: dict,
    timeout_seconds: int = 1200,
    poll_interval: int = 30,
) -> str:
    """
    Poll the pipeline status until it reaches a terminal state or times out.
    Returns the final status string.
    """
    url = f"{OM_BASE_URL}/services/ingestionPipelines/{pipeline_id}"
    deadline = time.monotonic() + timeout_seconds
    last_status = "unknown"

    while time.monotonic() < deadline:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        pipeline_status = resp.json().get("pipelineStatuses", {})
        last_status = pipeline_status.get("pipelineState", "unknown")
        logger.info("Pipeline %s status: %s", pipeline_id, last_status)

        if last_status in ("success", "failed", "partialSuccess"):
            return last_status

        time.sleep(poll_interval)

    logger.warning(
        "Pipeline %s did not complete within %d seconds. Last status: %s",
        pipeline_id,
        timeout_seconds,
        last_status,
    )
    return last_status


# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)


def _on_dbt_test_failure(context):
    _log.error(
        "dbt tests FAILED in DAG run %s — downstream OM ingestion skipped",
        context.get("run_id", "unknown"),
    )

def trigger_om_dbt_ingestion(**context) -> None:
    """
    Reads the three dbt artifact files produced by `dbt docs generate`,
    then triggers the pre-registered dbt ingestion pipeline in OpenMetadata.

    The pipeline must already exist in OM (created via UI or bootstrap script).
    This task only triggers it; OM fetches the files from the configured paths.
    """
    try:
        token = get_om_token()
    except Exception as exc:
        logger.warning("Skipping dbt OM ingestion: OpenMetadata unavailable/auth failed: %s", exc)
        context["task_instance"].xcom_push(key="dbt_ingestion_status", value="skipped_om_unavailable")
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Verify artifacts are present so we fail fast with a useful message
    artifacts_required = {
        "manifest.json": f"{DBT_PROJECT_DIR}/target/manifest.json",
        "catalog.json": f"{DBT_PROJECT_DIR}/target/catalog.json",
        "run_results.json": f"{DBT_PROJECT_DIR}/target/run_results.json",
    }
    missing = []
    for name, path in artifacts_required.items():
        if not os.path.exists(path):
            missing.append(path)
    if missing:
        raise FileNotFoundError(
            f"Required dbt artifact(s) not found. Run `dbt docs generate` first. "
            f"Missing: {missing}"
        )

    # Log artifact sizes for observability
    for name, path in artifacts_required.items():
        size_kb = os.path.getsize(path) // 1024
        logger.info("dbt artifact %s: %d KB", name, size_kb)

    # Resolve pipeline and trigger
    pipeline_id = _get_pipeline_id(DBT_PIPELINE_NAME, headers)
    if not pipeline_id:
        context["task_instance"].xcom_push(key="dbt_ingestion_status", value="skipped_missing_pipeline")
        return
    logger.info("Triggering dbt ingestion pipeline id=%s", pipeline_id)
    _trigger_pipeline(pipeline_id, headers)

    # Poll to completion (allow up to 20 min for large projects)
    final_status = _poll_pipeline_status(pipeline_id, headers, timeout_seconds=1200)
    logger.info("dbt ingestion pipeline finished with status: %s", final_status)

    if final_status == "failed":
        raise RuntimeError(f"dbt ingestion pipeline '{DBT_PIPELINE_NAME}' reported status=failed.")

    # Push status to XCom for downstream tasks / monitoring
    context["task_instance"].xcom_push(key="dbt_ingestion_status", value=final_status)


def trigger_om_trino_ingestion(**context) -> None:
    """
    Triggers the pre-registered Trino metadata ingestion pipeline in OpenMetadata.
    Runs after dbt ingestion so lineage links are established in the correct order.
    """
    try:
        token = get_om_token()
    except Exception as exc:
        logger.warning("Skipping trino OM ingestion: OpenMetadata unavailable/auth failed: %s", exc)
        context["task_instance"].xcom_push(key="trino_ingestion_status", value="skipped_om_unavailable")
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    pipeline_id = _get_pipeline_id(TRINO_PIPELINE_NAME, headers)
    if not pipeline_id:
        context["task_instance"].xcom_push(key="trino_ingestion_status", value="skipped_missing_pipeline")
        return
    logger.info("Triggering Trino metadata ingestion pipeline id=%s", pipeline_id)
    _trigger_pipeline(pipeline_id, headers)

    # Poll to completion (allow up to 20 min)
    final_status = _poll_pipeline_status(pipeline_id, headers, timeout_seconds=1200)
    logger.info("Trino ingestion pipeline finished with status: %s", final_status)

    if final_status == "failed":
        raise RuntimeError(
            f"Trino ingestion pipeline '{TRINO_PIPELINE_NAME}' reported status=failed."
        )

    context["task_instance"].xcom_push(key="trino_ingestion_status", value=final_status)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="dbt_to_om_dag",
    default_args=default_args,
    description="Run dbt CDM build, tests, docs, then sync artifacts to OpenMetadata",
    schedule_interval=None,          # API-triggered only; set a cron here if needed
    start_date=days_ago(1),
    catchup=False,
    tags=["datalens", "dbt", "cdm", "openmetadata"],
    max_active_runs=3,
    dagrun_timeout=timedelta(hours=4),
    doc_md="""
## dbt → OpenMetadata DAG

**Purpose:** Build the CDM, run all data quality tests, generate dbt docs,
and publish the result to OpenMetadata so lineage + column descriptions are
always up-to-date.

**Task order:**
```
dbt_deps → dbt_run_staging → dbt_run_cdm → dbt_test
         → dbt_docs_generate → om_dbt_ingestion → om_trino_ingestion
```

**Trigger:** Triggered via Airflow API after every successful CDM deployment.
Set `schedule_interval` to a cron string to also run on a schedule.

**Prerequisites:**
- OM ingestion pipelines named `dbt_ingestion_pipeline` and
  `trino_metadata_pipeline` must exist in OpenMetadata.
- `OM_HOST`, `OM_PORT`, `OM_ADMIN_EMAIL`, `OM_ADMIN_PASSWORD` env vars set.
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
    # Step 4 – Run all tests, persist failures to a table for inspection
    # -----------------------------------------------------------------------
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt test --store-failures --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        on_failure_callback=_on_dbt_test_failure,
        doc_md="Execute all dbt schema / data tests. Failures are stored in a test failures table.",
    )

    # -----------------------------------------------------------------------
    # Step 5 – Generate docs (produces manifest.json + catalog.json)
    # -----------------------------------------------------------------------
    dbt_docs_generate = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt docs generate --profiles-dir {DBT_PROJECT_DIR} --target prod"
        ),
        doc_md=(
            "Generate dbt documentation artifacts: manifest.json, catalog.json, "
            "run_results.json. These are consumed by OpenMetadata in the next step."
        ),
    )

    # -----------------------------------------------------------------------
    # Step 6 – Publish dbt artifacts to OpenMetadata
    # -----------------------------------------------------------------------
    om_dbt_ingestion = PythonOperator(
        task_id="om_dbt_ingestion",
        python_callable=trigger_om_dbt_ingestion,
        doc_md=(
            "Verify dbt artifact files exist, then trigger the pre-registered "
            "dbt ingestion pipeline in OpenMetadata. Polls until completion."
        ),
    )

    # -----------------------------------------------------------------------
    # Step 7 – Refresh Trino metadata in OpenMetadata
    # -----------------------------------------------------------------------
    om_trino_ingestion = PythonOperator(
        task_id="om_trino_ingestion",
        python_callable=trigger_om_trino_ingestion,
        doc_md=(
            "Trigger Trino metadata re-ingestion so any new tables/columns "
            "created by dbt are reflected in OpenMetadata immediately."
        ),
    )

    # -----------------------------------------------------------------------
    # Pipeline dependency chain
    # -----------------------------------------------------------------------
    (
        wait_for_trino
        >> dbt_deps
        >> dbt_run_staging
        >> dbt_run_cdm
        >> dbt_test
        >> dbt_docs_generate
        >> om_dbt_ingestion
        >> om_trino_ingestion
    )
