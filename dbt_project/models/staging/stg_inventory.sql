{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_inventory
  -------------
  Cleans and enriches inventory snapshot data.
  Key transformations:
    - Join to products for sku and product_name
    - Join to stores for store_name and city
    - Derive available_quantity = quantity_on_hand - quantity_reserved
    - Add low_stock_flag for items at or below available threshold of 10
*/

WITH source_inventory AS (

    SELECT *
    FROM {{ source('retail', 'inventory_snapshots') }}

),

source_products AS (

    SELECT
        product_id,
        sku,
        product_name,
        reorder_level
    FROM {{ source('retail', 'products') }}

),

source_stores AS (

    SELECT
        store_id,
        store_name,
        city
    FROM {{ source('retail', 'stores') }}

),

joined AS (

    SELECT
        -- Primary key
        inv.snapshot_id,

        -- Foreign keys
        inv.product_id,
        inv.store_id,

        -- Enriched product context
        p.sku,
        TRIM(p.product_name)                                              AS product_name,

        -- Enriched store context
        TRIM(s.store_name)                                                AS store_name,
        TRIM(s.city)                                                      AS city,

        -- Snapshot timing
        CAST(inv.snapshot_date AS DATE)                                   AS snapshot_date,

        -- Inventory quantities
        inv.quantity_on_hand,
        inv.quantity_reserved,

        -- Derived: available stock after reservations
        (inv.quantity_on_hand - COALESCE(inv.quantity_reserved, 0))       AS available_quantity,

        -- Low stock flag: available quantity at or below threshold of 10
        CASE
            WHEN (inv.quantity_on_hand - COALESCE(inv.quantity_reserved, 0)) <= 10
            THEN TRUE
            ELSE FALSE
        END                                                               AS low_stock_flag,

        -- Reorder status
        inv.reorder_triggered,

        -- Audit
        current_timestamp                                                 AS dbt_updated_at

    FROM source_inventory AS inv
    LEFT JOIN source_products AS p
        ON inv.product_id = p.product_id
    LEFT JOIN source_stores AS s
        ON inv.store_id = s.store_id

)

SELECT *
FROM joined
