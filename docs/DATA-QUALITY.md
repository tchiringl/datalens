# DataLens — Data Quality Reference

This document describes the two-tier data quality system, the tests applied to each model, the statistical checks, the custom macro, and how test results flow through to OpenMetadata.

---

## Overview

DataLens uses a two-tier DQ system:

**Tier 1 — dbt tests (pass/fail guardrails)**
Declarative tests defined in `schema.yml` files. They run via `dbt test` and produce binary pass/fail outcomes. Some are configured as `error` severity (they block the pipeline if they fail) and some as `warn` severity (they flag the issue without stopping downstream models).

**Tier 2 — Profiling models (continuous statistics)**
dbt models in `dbt_project/models/profiling/` that materialise daily metric snapshots into Iceberg tables. These produce quantitative statistics — null rates, distributions, row counts, percentages — that trend over time and feed the OpenMetadata DQ dashboard.

The two tiers are complementary. Tests catch outright violations. Profiling models catch gradual drift that no single test would flag.

---

## dbt Test Tiers

### Tier 1 — ERROR (blocks pipeline)

These tests use the default `severity: error`. If they fail, `dbt test` exits non-zero and Airflow marks the task as failed. Downstream tasks do not run.

| Test type | What it checks |
|-----------|---------------|
| `not_null` | Column contains no NULL values |
| `unique` | All values in the column are distinct |
| `relationships` | Every foreign key value exists in the referenced model's primary key column |
| `accepted_values` | Column values are members of a specified set |
| `dbt_utils.expression_is_true` | A SQL expression evaluates to true for every row (used for numeric range enforcement, e.g. `unit_price > 0`) |
| `dbt_expectations.expect_column_values_to_be_between` (error) | Numeric or date values fall within a specified range — used on `order_date` |

### Tier 2 — WARN (flagged, does not block)

These tests carry `severity: warn`. They appear in the dbt test output and in the OpenMetadata DQ dashboard but do not cause the pipeline to stop.

| Test type | What it checks |
|-----------|---------------|
| `dbt_expectations.expect_table_row_count_to_be_between` | Table has at least a minimum number of rows |
| `dbt_expectations.expect_column_values_to_be_between` (warn) | Numeric values fall within an expected range |
| `dbt_expectations.expect_column_mean_to_be_between` | Column mean stays within a historically normal band |
| `dbt_expectations.expect_column_values_to_match_regex` | Column values match a regex pattern (e.g. email format) |
| `dbt_expectations.expect_column_values_to_not_be_null` (mostly) | At least a specified fraction of rows are non-null |
| `alert_high_null_rate` | Custom macro — null rate exceeds a configurable threshold |

---

## Profiling Models

These models live in `dbt_project/models/profiling/` and materialise as Iceberg tables. Each runs nightly and appends a new snapshot row dated to the current execution date.

| Model | What it measures | Key metrics |
|-------|-----------------|-------------|
| `profile_fact_orders` | Order completeness and distribution | `total_rows`, `distinct_customers`, null rates per column, `p95_line_total` |
| `profile_dim_customers` | Customer data completeness | `email_null_pct`, `phone_null_pct`, `unknown_segment_pct` |
| `profile_fact_inventory` | Inventory health | `zero_stock_pct` (rows where `quantity_on_hand = 0`), `negative_available_pct` |
| `profile_fact_returns` | Return rate quality | `return_rate_pct` (returns / total orders), `avg_refund` |

These metrics are queryable directly via Trino and are also ingested by the OpenMetadata profiler DAG, which populates the "Data Profiler" tab on each table's asset page.

---

## Statistical Tests (dbt_expectations)

### fact_orders

```yaml
# Table-level
tests:
  - dbt_expectations.expect_table_row_count_to_be_between:
      min_value: 1000
      severity: warn

# Column-level
columns:
  - name: line_total_fixed
    tests:
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: 0
          max_value: 100000
          severity: warn
      - dbt_expectations.expect_column_mean_to_be_between:
          min_value: 10
          max_value: 5000
          severity: warn

  - name: order_date
    tests:
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: "'2020-01-01'"
          max_value: "'2030-12-31'"
          severity: error

  - name: quantity
    tests:
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: 1
          max_value: 1000
          severity: warn
```

### dim_customers — email validation

```yaml
columns:
  - name: email
    tests:
      - dbt_expectations.expect_column_values_to_match_regex:
          regex: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
          severity: warn
      - dbt_expectations.expect_column_values_to_not_be_null:
          mostly: 0.95
          severity: warn
```

`mostly: 0.95` means the test passes as long as at least 95% of rows are non-null. The remaining 5% are handled by the `unknown@noemail.com` substitution in the staging layer.

### fact_inventory — composite uniqueness

```yaml
tests:
  - dbt_utils.unique_combination_of_columns:
      combination_of_columns:
        - product_id
        - store_id
        - snapshot_date
```

Each inventory snapshot must be unique per product, store, and date. Duplicate combinations would indicate a double-ingestion.

### fact_returns — FK to fact_orders

```yaml
columns:
  - name: order_item_id
    tests:
      - not_null
      - relationships:
          to: ref('fact_orders')
          field: order_item_id
```

Every return must reference a valid order line item. Orphaned returns (no matching order) are a hard error.

---

## Custom Macro: `alert_high_null_rate`

**File:** `dbt_project/macros/alert_high_null_rate.sql`

**Signature:**

```sql
{% test alert_high_null_rate(model, column_name, threshold=0.05) %}
    SELECT COUNT(*) AS failing_rows
    FROM {{ model }}
    WHERE {{ column_name }} IS NULL
    HAVING COUNT(*) > (SELECT COUNT(*) * {{ threshold }} FROM {{ model }})
{% endtest %}
```

**What it does:** Counts NULL rows in `column_name`. If the count exceeds `threshold` multiplied by the total row count, the test fails. The default threshold is 5% (0.05). The test is a dbt generic test, so it can be applied to any column in any model via `schema.yml`.

**Example usage — `fact_orders.store_id` with a 50% threshold:**

```yaml
- name: store_id
  description: "Foreign key to dim_stores. NULL for online orders."
  tests:
    - alert_high_null_rate:
        threshold: 0.5
        severity: warn
```

A threshold of 0.5 means the test warns when more than 50% of orders have no store (indicating an unexpectedly high proportion of online orders, or a store_id ingestion problem). The threshold is business-context-dependent — set it to a value that represents a genuine anomaly for the column in question.

---

## How to Add a New Test

**Basic not_null:**

```yaml
columns:
  - name: your_column
    tests:
      - not_null
```

**dbt_expectations range check:**

```yaml
columns:
  - name: your_numeric_column
    tests:
      - dbt_expectations.expect_column_values_to_be_between:
          min_value: 0
          max_value: 10000
          severity: warn
```

**Custom macro (alert_high_null_rate):**

```yaml
columns:
  - name: your_nullable_column
    tests:
      - alert_high_null_rate:
          threshold: 0.1   # warn if more than 10% are null
          severity: warn
```

After adding a test to `schema.yml`, run:

```bash
docker compose exec api bash -c "cd /dbt && dbt test --select your_model_name"
```

Confirm the new test appears in the output and passes before committing.

---

## How Test Results Flow to OpenMetadata

1. **Airflow DAG runs `dbt test`** with the `--store-failures` flag. This writes failure details into Trino/Iceberg tables so the results are queryable.

2. **Airflow DAG triggers OM dbt ingestion.** The `dbt_to_om_dag` calls the OpenMetadata ingestion pipeline, which reads the dbt `manifest.json`, `catalog.json`, and `run_results.json` from the dbt target directory.

3. **OpenMetadata parses test results.** The ingestion connector maps dbt test outcomes to OpenMetadata's data quality test format and associates each result with the correct table and column asset in the catalog.

4. **Results appear in the DQ dashboard.** Each table's asset page in OpenMetadata shows a "Data Quality" tab with pass/fail history, severity levels, and timestamps. The `om_profiling_dag` separately triggers the OpenMetadata column profiler, which populates the "Data Profiler" tab with the metric snapshots produced by the profiling models.

The full pipeline runs nightly. Engineers can also trigger the Airflow DAGs manually from the Airflow UI at [http://localhost:8082](http://localhost:8082).

---

## Quality SLAs per Model

| Model | Critical tests — ERROR (blocks pipeline) | Warning tests — WARN (flagged only) |
|-------|------------------------------------------|--------------------------------------|
| `fact_orders` | `order_item_id` not_null + unique; `order_id` not_null; `customer_id` not_null + FK to dim_customers; `product_id` not_null + FK to dim_products; `order_date` not_null + range 2020–2030; `line_total_fixed` not_null + `>= 0` | Row count >= 1000; `line_total_fixed` range 0–100000; `line_total_fixed` mean 10–5000; `quantity` range 1–1000; `store_id` null rate <= 50% |
| `dim_customers` | `customer_id` not_null + unique; `customer_code` not_null; `email` not_null; `loyalty_tier` accepted_values; `customer_segment` accepted_values | Email regex format; email >= 95% non-null |
| `dim_products` | `product_id` not_null + unique; `sku` not_null + unique; `product_name` not_null; `unit_price` not_null + `> 0`; `price_tier` accepted_values | `cost_price >= 0`; `margin_pct` derived check |
| `fact_inventory` | `snapshot_id` not_null + unique; `product_id` not_null + FK; `store_id` not_null + FK; `snapshot_date` not_null; composite unique on (product_id, store_id, snapshot_date); `quantity_on_hand >= 0`; `quantity_reserved >= 0`; `available_quantity >= 0` | — |
| `fact_returns` | `return_id` not_null + unique; `order_id` not_null + FK to fact_orders; `order_item_id` not_null + FK to fact_orders; `return_date` not_null; `refund_amount >= 0` | — |
