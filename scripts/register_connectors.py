#!/usr/bin/env python3
"""
Register all data source connectors in OpenMetadata and create Trino catalogs.
Run this after `make up` and OpenMetadata is healthy.

Usage:
    python3 scripts/register_connectors.py
    python3 scripts/register_connectors.py --dry-run
"""

import argparse
import json
import os
import sys
import time

import requests

OM_BASE = os.getenv("OM_BASE_URL", "http://localhost:8585/api/v1")
OM_USER = os.getenv("OM_ADMIN_USER", "admin")
OM_PASS = os.getenv("OM_ADMIN_PASSWORD", "admin")

CONNECTORS = [
    {
        "name": "trinodatalens",
        "displayName": "Trino Data Lens",
        "description": "Primary Trino federated query engine — connects postgres, iceberg, redshift, bigquery catalogs",
        "serviceType": "Trino",
        "connection": {
            "config": {
                "type": "Trino",
                "hostPort": "trino:8080",
                "username": "admin",
                "catalog": "postgres",
                "params": {"http_scheme": "http"},
            }
        },
    },
    {
        "name": "postgres_retail",
        "displayName": "PostgreSQL Retail (Source)",
        "description": "Operational retail database — customers, orders, products, stores",
        "serviceType": "Postgres",
        "connection": {
            "config": {
                "type": "Postgres",
                "hostPort": "postgres:5432",
                "username": os.getenv("POSTGRES_USER", "datalens"),
                "authType": {"password": os.getenv("POSTGRES_PASSWORD", "datalens123")},
                "database": os.getenv("POSTGRES_DB", "retail"),
            }
        },
    },
    {
        "name": "iceberg_warehouse",
        "displayName": "Iceberg / MinIO Warehouse",
        "description": "Lakehouse storage — CDM models and raw Wayfair ingestion layer",
        "serviceType": "Trino",
        "connection": {
            "config": {
                "type": "Trino",
                "hostPort": "trino:8080",
                "username": "admin",
                "catalog": "iceberg",
                "params": {"http_scheme": "http"},
            }
        },
    },
    # FUTURE: uncomment and fill in credentials when Redshift is available
    # {
    #     "name": "redshift_analytics",
    #     "displayName": "Redshift Analytics",
    #     "serviceType": "Redshift",
    #     "connection": {
    #         "config": {
    #             "type": "Redshift",
    #             "hostPort": "your-cluster.redshift.amazonaws.com:5439",
    #             "username": "redshift_user",
    #             "authType": {"password": "redshift_password"},
    #             "database": "dev",
    #         }
    #     },
    # },
    # FUTURE: uncomment and provide GCP service account JSON for BigQuery
    # {
    #     "name": "bigquery_analytics",
    #     "displayName": "BigQuery Analytics",
    #     "serviceType": "BigQuery",
    #     "connection": {
    #         "config": {
    #             "type": "BigQuery",
    #             "credentials": {
    #                 "gcpConfig": {
    #                     "type": "service_account",
    #                     "projectId": "your-gcp-project-id",
    #                 }
    #             },
    #         }
    #     },
    # },
]


def get_token() -> str:
    resp = requests.post(
        f"{OM_BASE}/users/login",
        json={"email": "admin@open-metadata.org", "password": OM_PASS},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["accessToken"]


def wait_for_om(max_retries: int = 20, delay: int = 10) -> None:
    print(f"Waiting for OpenMetadata at {OM_BASE}...")
    for i in range(max_retries):
        try:
            r = requests.get(f"{OM_BASE}/system/status", timeout=5)
            if r.status_code == 200:
                print("  OpenMetadata is ready.")
                return
        except requests.ConnectionError:
            pass
        print(f"  Not ready yet ({i+1}/{max_retries}), retrying in {delay}s...")
        time.sleep(delay)
    print("ERROR: OpenMetadata did not become ready in time.", file=sys.stderr)
    sys.exit(1)


def service_exists(name: str, token: str) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{OM_BASE}/services/databaseServices/name/{name}", headers=headers, timeout=10)
    return r.status_code == 200


def register_connector(connector: dict, token: str, dry_run: bool = False) -> None:
    name = connector["name"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    if service_exists(name, token):
        print(f"  [skip]   '{name}' already registered")
        return

    payload = {
        "name": name,
        "displayName": connector.get("displayName", name),
        "description": connector.get("description", ""),
        "serviceType": connector["serviceType"],
        "connection": connector["connection"],
    }

    if dry_run:
        print(f"  [dry-run] Would register: {name} ({connector['serviceType']})")
        print(f"            Payload: {json.dumps(payload, indent=2)[:200]}...")
        return

    r = requests.post(
        f"{OM_BASE}/services/databaseServices",
        headers=headers,
        json=payload,
        timeout=15,
    )
    if r.status_code in (200, 201):
        print(f"  [ok]     Registered '{name}' ({connector['serviceType']})")
    else:
        print(f"  [fail]   Failed to register '{name}': {r.status_code} — {r.text[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Register Data Lens connectors in OpenMetadata")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    args = parser.parse_args()

    if not args.dry_run:
        wait_for_om()

    token = get_token() if not args.dry_run else "dry-run-token"

    print(f"\nRegistering {len(CONNECTORS)} connectors{'  [DRY RUN]' if args.dry_run else ''}:")
    for connector in CONNECTORS:
        register_connector(connector, token, dry_run=args.dry_run)

    print("\nDone. Run the ingestion pipelines next:")
    print("  make airflow-trigger DAG=dbt_to_om_dag")
    print("  Or open http://localhost:8082 → trigger 'dbt_to_om_dag'")


if __name__ == "__main__":
    main()
