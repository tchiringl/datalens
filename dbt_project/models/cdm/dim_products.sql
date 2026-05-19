{{
    config(
        materialized  = 'incremental',
        schema        = 'cdm',
        unique_key    = 'product_id',
        on_schema_change = 'append_new_columns'
    )
}}

/*
  dim_products
  ------------
  CDM Product dimension table.
  Grain: one row per active product.

  Incremental strategy:
    - On full refresh: loads all active products
    - On incremental run: loads products added/updated since last run

  Derived columns:
    - is_low_stock: TRUE when stock_quantity <= reorder_level
    - price_tier: categorical bucketing of unit_price
*/

WITH stg_products AS (

    SELECT *
    FROM {{ ref('stg_products') }}

    {% if is_incremental() %}
    -- Load only products created after the latest we already have
    WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}

),

enriched AS (

    SELECT
        -- Primary key
        product_id,

        -- Business key
        sku,

        -- Product identity
        product_name,
        category_id,
        category_name,
        brand,

        -- Pricing
        unit_price,
        cost_price,
        margin_pct,

        -- Physical
        weight_kg,

        -- Inventory status
        stock_quantity,
        reorder_level,

        -- Derived: low stock flag
        CASE
            WHEN stock_quantity IS NOT NULL
             AND reorder_level IS NOT NULL
             AND stock_quantity <= reorder_level
            THEN TRUE
            ELSE FALSE
        END                                         AS is_low_stock,

        -- Derived: price tier bucketing
        CASE
            WHEN unit_price < 25                    THEN 'Budget'
            WHEN unit_price >= 25   AND unit_price < 100  THEN 'Mid-range'
            WHEN unit_price >= 100  AND unit_price < 500  THEN 'Premium'
            WHEN unit_price >= 500                  THEN 'Luxury'
            ELSE 'Unknown'
        END                                         AS price_tier,

        -- Timestamps
        created_at,

        -- Audit
        dbt_updated_at

    FROM stg_products

)

SELECT *
FROM enriched
