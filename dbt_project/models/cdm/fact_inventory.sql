{{
    config(
        materialized  = 'incremental',
        schema        = 'cdm',
        unique_key    = 'snapshot_id',
        on_schema_change = 'append_new_columns'
    )
}}

/*
  fact_inventory
  --------------
  Inventory snapshot fact table.
  Grain: one row per product × store × snapshot_date.

  Source: stg_inventory (already enriched with product and store names)

  Incremental strategy:
    Load snapshots whose snapshot_date is later than the latest date
    already present in the fact table.

  Columns mirror stg_inventory with product_id and store_id as dimension keys,
  plus reorder_triggered for supply-chain alerting.
*/

WITH stg_inventory AS (

    SELECT *
    FROM {{ ref('stg_inventory') }}

    {% if is_incremental() %}
    WHERE snapshot_date > (SELECT MAX(snapshot_date) FROM {{ this }})
    {% endif %}

)

SELECT
    -- Primary key (snapshot surrogate)
    snapshot_id,

    -- Dimension foreign keys
    product_id,
    store_id,

    -- Snapshot timing
    snapshot_date,

    -- Inventory quantities
    quantity_on_hand,
    quantity_reserved,
    available_quantity,

    -- Derived flags
    low_stock_flag,
    reorder_triggered,

    -- Audit
    dbt_updated_at

FROM stg_inventory
