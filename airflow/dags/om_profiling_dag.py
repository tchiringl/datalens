"""
om_profiling_dag.py
-------------------
Triggers OpenMetadata data profiling pipelines for all registered database
services.

Architecture note (from design doc):
  Profiling is intentionally DECOUPLED from source onboarding because:
    - Profiling takes 15–30 min per service (vs. seconds for metadata ingest)
    - Profiling puts load on source systems and Trino; we don't want this
      to block or slow the nightly metadata refresh.
    - Profiling is most useful on a weekly cadence, not daily.

Trigger strategy: scheduled weekly (Sunday 02:00 UTC) OR via Airflow API.

Task order:
  get_registered_services
    → trigger_profiling_pipelines   (for each active service in parallel via Dynamic Tasks)
    → report_profiling_summary
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import os
import time
import logging
import requests
import base64
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OM_HOST = os.getenv("OM_HOST", "openmetadata-server")
OM_PORT = os.getenv("OM_PORT", "8585")
OM_BASE_URL = f"http://{OM_HOST}:{OM_PORT}/api/v1"
OM_ADMIN_EMAIL = os.getenv("OM_ADMIN_EMAIL", "admin@openmetadata.org")
OM_ADMIN_PASSWORD = os.getenv("OM_ADMIN_PASSWORD", "admin")

# Only trigger profiling for services whose type matches one of these
SUPPORTED_SERVICE_TYPES = os.getenv(
    "OM_PROFILING_SERVICE_TYPES", "Trino,Postgres,BigQuery,Redshift"
).split(",")

# How long (seconds) to wait for all profiling pipelines to finish
PROFILING_TIMEOUT_SECONDS = int(os.getenv("OM_PROFILING_TIMEOUT_SECONDS", str(20 * 60)))
POLL_INTERVAL_SECONDS = int(os.getenv("OM_PROFILING_POLL_INTERVAL", "45"))

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
default_args = {
    "owner": "datalens",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=1),
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_om_token() -> str:
    """Authenticate against OpenMetadata and return a JWT bearer token."""
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
            last_error = ValueError(f"No accessToken in OM login response: {resp.text[:500]}")
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"OpenMetadata login failed for configured users. Last error: {last_error}")


def _build_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _list_database_services(headers: Dict[str, str]) -> List[Dict]:
    """
    Return all registered database services from OpenMetadata.
    Handles pagination via the `after` cursor.
    """
    services: List[Dict] = []
    url = f"{OM_BASE_URL}/services/databaseServices"
    params = {"limit": 50, "fields": "id,name,serviceType,pipelines"}
    after: Optional[str] = None

    while True:
        if after:
            params["after"] = after
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        page_data = body.get("data", [])
        services.extend(page_data)

        paging = body.get("paging", {})
        after = paging.get("after")
        if not after:
            break

    logger.info("Found %d database service(s) in OpenMetadata.", len(services))
    return services


def _list_ingestion_pipelines(
    service_id: str, headers: Dict[str, str]
) -> List[Dict]:
    """
    Return ingestion pipelines associated with a specific database service.
    Filters to Profiler-type pipelines.
    """
    url = f"{OM_BASE_URL}/services/ingestionPipelines"
    params = {"service": service_id, "pipelineType": "profiler", "limit": 50}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _trigger_pipeline(pipeline_id: str, headers: Dict[str, str]) -> bool:
    """
    Trigger an ingestion pipeline.  Returns True on success, False on error.
    """
    url = f"{OM_BASE_URL}/services/ingestionPipelines/trigger/{pipeline_id}"
    resp = requests.post(url, headers=headers, timeout=30)
    if resp.status_code in (200, 201, 202):
        logger.info("Triggered pipeline %s (HTTP %d).", pipeline_id, resp.status_code)
        return True
    logger.warning(
        "Failed to trigger pipeline %s: HTTP %d – %s",
        pipeline_id,
        resp.status_code,
        resp.text[:300],
    )
    return False


def _get_pipeline_status(pipeline_id: str, headers: Dict[str, str]) -> str:
    """Fetch the latest pipeline status string."""
    url = f"{OM_BASE_URL}/services/ingestionPipelines/{pipeline_id}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    statuses = resp.json().get("pipelineStatuses", {})
    return statuses.get("pipelineState", "unknown")


def _poll_until_done(
    pipeline_ids: List[str],
    headers: Dict[str, str],
    timeout: int,
    interval: int,
) -> Dict[str, str]:
    """
    Poll all pipeline IDs until every one reaches a terminal state or the
    global timeout is exceeded.

    Returns a dict mapping pipeline_id → final_status.
    """
    terminal_states = {"success", "failed", "partialSuccess"}
    statuses: Dict[str, str] = {pid: "running" for pid in pipeline_ids}
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        pending = [pid for pid, st in statuses.items() if st not in terminal_states]
        if not pending:
            break

        for pid in pending:
            try:
                st = _get_pipeline_status(pid, headers)
                statuses[pid] = st
                logger.info("Pipeline %s → %s", pid, st)
            except Exception as exc:
                logger.warning("Error polling pipeline %s: %s", pid, exc)

        still_pending = [pid for pid, st in statuses.items() if st not in terminal_states]
        if not still_pending:
            break
        logger.info("%d pipeline(s) still running; sleeping %ds.", len(still_pending), interval)
        time.sleep(interval)

    # Mark timed-out pipelines
    for pid, st in statuses.items():
        if st not in terminal_states:
            logger.warning("Pipeline %s timed out (last status: %s).", pid, st)
            statuses[pid] = "timeout"

    return statuses


# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------

def get_registered_services(**context) -> None:
    """
    Fetch all active database services from OM, filter to supported types,
    and push the list to XCom for the next task.
    """
    token = _get_om_token()
    headers = _build_headers(token)

    all_services = _list_database_services(headers)

    active_services = [
        svc for svc in all_services
        if svc.get("serviceType") in SUPPORTED_SERVICE_TYPES
    ]

    logger.info(
        "Filtered to %d service(s) with supported types %s.",
        len(active_services),
        SUPPORTED_SERVICE_TYPES,
    )

    for svc in active_services:
        logger.info(
            "  Service: name=%s  type=%s  id=%s",
            svc.get("name"),
            svc.get("serviceType"),
            svc.get("id"),
        )

    context["task_instance"].xcom_push(key="active_services", value=active_services)
    context["task_instance"].xcom_push(key="service_count", value=len(active_services))


def trigger_profiling_pipelines(**context) -> None:
    """
    For each active service retrieved in the previous task:
      1. List all Profiler-type ingestion pipelines attached to that service.
      2. Trigger each profiler pipeline.
      3. Poll all triggered pipelines until completion or global timeout.
      4. Push a summary dict to XCom.

    A service with no profiler pipeline registered is logged as a warning
    (not a failure) — the operator should create one in the OM UI.
    """
    ti = context["task_instance"]
    active_services: List[Dict] = ti.xcom_pull(
        task_ids="get_registered_services", key="active_services"
    )

    if not active_services:
        logger.warning("No active services found. Nothing to profile.")
        ti.xcom_push(key="triggered_pipelines", value={})
        ti.xcom_push(key="final_statuses", value={})
        return

    token = _get_om_token()
    headers = _build_headers(token)

    triggered: Dict[str, str] = {}   # pipeline_id → service_name
    skipped_services: List[str] = []

    for svc in active_services:
        svc_name = svc.get("name", "unknown")
        svc_id = svc.get("id")

        pipelines = _list_ingestion_pipelines(svc_id, headers)
        if not pipelines:
            logger.warning(
                "Service '%s' has no Profiler ingestion pipeline. "
                "Create one in the OpenMetadata UI (Ingestion > Add Profiler).",
                svc_name,
            )
            skipped_services.append(svc_name)
            continue

        for pipeline in pipelines:
            pid = pipeline.get("id")
            pname = pipeline.get("name", pid)
            logger.info("Triggering profiler pipeline '%s' for service '%s'.", pname, svc_name)
            ok = _trigger_pipeline(pid, headers)
            if ok:
                triggered[pid] = svc_name
            else:
                logger.warning(
                    "Trigger failed for pipeline '%s' (service '%s'). "
                    "It will not be polled.",
                    pname,
                    svc_name,
                )

    ti.xcom_push(key="triggered_pipelines", value=triggered)
    ti.xcom_push(key="skipped_services", value=skipped_services)

    if not triggered:
        logger.warning("No profiling pipelines were successfully triggered.")
        ti.xcom_push(key="final_statuses", value={})
        return

    logger.info(
        "Triggered %d profiling pipeline(s). Polling for completion "
        "(timeout=%ds, interval=%ds)...",
        len(triggered),
        PROFILING_TIMEOUT_SECONDS,
        POLL_INTERVAL_SECONDS,
    )

    final_statuses = _poll_until_done(
        pipeline_ids=list(triggered.keys()),
        headers=headers,
        timeout=PROFILING_TIMEOUT_SECONDS,
        interval=POLL_INTERVAL_SECONDS,
    )

    ti.xcom_push(key="final_statuses", value=final_statuses)

    # Log per-service outcome
    for pid, status in final_statuses.items():
        svc_name = triggered[pid]
        logger.info("Service '%s' profiling pipeline %s → %s", svc_name, pid, status)


def report_profiling_summary(**context) -> None:
    """
    Pull results from XCom and emit a structured summary log.
    Raises an AirflowException if ANY pipeline reported 'failed'.
    """
    from airflow.exceptions import AirflowException

    ti = context["task_instance"]
    triggered: Dict[str, str] = ti.xcom_pull(
        task_ids="trigger_profiling_pipelines", key="triggered_pipelines"
    ) or {}
    final_statuses: Dict[str, str] = ti.xcom_pull(
        task_ids="trigger_profiling_pipelines", key="final_statuses"
    ) or {}
    skipped: List[str] = ti.xcom_pull(
        task_ids="trigger_profiling_pipelines", key="skipped_services"
    ) or []
    service_count: int = ti.xcom_pull(
        task_ids="get_registered_services", key="service_count"
    ) or 0

    success_count = sum(1 for s in final_statuses.values() if s == "success")
    partial_count = sum(1 for s in final_statuses.values() if s == "partialSuccess")
    failed_count  = sum(1 for s in final_statuses.values() if s == "failed")
    timeout_count = sum(1 for s in final_statuses.values() if s == "timeout")

    summary_lines = [
        "=" * 60,
        "  PROFILING SUMMARY",
        "=" * 60,
        f"  Total services discovered : {service_count}",
        f"  Services with no pipeline : {len(skipped)} ({', '.join(skipped) if skipped else 'none'})",
        f"  Pipelines triggered       : {len(triggered)}",
        f"  Completed successfully    : {success_count}",
        f"  Partial success           : {partial_count}",
        f"  Failed                    : {failed_count}",
        f"  Timed out                 : {timeout_count}",
        "=" * 60,
    ]
    for line in summary_lines:
        logger.info(line)

    if failed_count > 0:
        failed_pipelines = [
            f"{triggered.get(pid, pid)} ({pid})"
            for pid, st in final_statuses.items()
            if st == "failed"
        ]
        raise AirflowException(
            f"{failed_count} profiling pipeline(s) reported status=failed: "
            + ", ".join(failed_pipelines)
        )

    if timeout_count > 0:
        logger.warning(
            "%d pipeline(s) exceeded the %d-second timeout. "
            "Consider increasing OM_PROFILING_TIMEOUT_SECONDS or "
            "reducing the profiling scope in the OM pipeline config.",
            timeout_count,
            PROFILING_TIMEOUT_SECONDS,
        )


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="om_profiling_dag",
    default_args=default_args,
    description=(
        "Weekly OpenMetadata data profiling for all registered database services. "
        "Intentionally decoupled from source onboarding (~15-30 min execution)."
    ),
    schedule_interval="0 2 * * 0",   # Every Sunday at 02:00 UTC
    start_date=days_ago(7),
    catchup=False,
    tags=["datalens", "openmetadata", "profiling"],
    max_active_runs=1,
    doc_md="""
## OpenMetadata Profiling DAG

**Purpose:** Trigger data profiling pipelines for every registered database
service in OpenMetadata, then report the outcomes.

**Why decoupled from onboarding?**
Profiling can take 15–30 minutes per service and puts non-trivial load on
both Trino and the source databases.  Running it separately prevents it from
blocking the nightly metadata refresh and allows independent scheduling.

**Supported service types** (configurable via `OM_PROFILING_SERVICE_TYPES` env var):
- Trino
- Postgres
- BigQuery
- Redshift

**Prerequisites:**
- Each service must have a *Profiler* ingestion pipeline already registered
  in OpenMetadata (create via OM UI → service → Ingestion tab → Add Profiler).
- `OM_HOST`, `OM_PORT`, `OM_ADMIN_EMAIL`, `OM_ADMIN_PASSWORD` env vars must be set.

**Timeout:** configurable via `OM_PROFILING_TIMEOUT_SECONDS` (default 1200 s / 20 min).
""",
) as dag:

    get_services = PythonOperator(
        task_id="get_registered_services",
        python_callable=get_registered_services,
        doc_md="Fetch all active database services from OM and push them to XCom.",
    )

    trigger_profiling = PythonOperator(
        task_id="trigger_profiling_pipelines",
        python_callable=trigger_profiling_pipelines,
        doc_md=(
            "For each active service, find its Profiler pipeline, trigger it, "
            "then poll until completion or timeout."
        ),
    )

    summarise = PythonOperator(
        task_id="report_profiling_summary",
        python_callable=report_profiling_summary,
        doc_md="Log a structured summary table and raise if any pipeline failed.",
        trigger_rule="all_done",   # run even if upstream had failures, so we always get a report
    )

    get_services >> trigger_profiling >> summarise
