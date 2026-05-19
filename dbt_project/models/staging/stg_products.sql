{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_products
  ------------
  Cleans and enriches product data.
  Key transformations:
    - Join to product_categories to resolve category_name
    - Derive margin_pct as rounded percentage
    - Standardize brand to UPPER
    - Filter to active products only
*/

WITH source_products AS (

    SELECT *
    FROM {{ source('retail', 'products') }}

),

source_categories AS (

    SELECT *
    FROM {{ source('retail', 'product_categories') }}

),

joined AS (

    SELECT
        -- Primary key
        p.product_id,

        -- Business key
        TRIM(p.sku)                                                                   AS sku,

        -- Product details
        TRIM(p.product_name)                                                          AS product_name,

        -- Category (resolved from join)
        p.category_id,
        TRIM(c.category_name)                                                         AS category_name,

        -- Brand: standardized to UPPER
        UPPER(TRIM(p.brand))                                                          AS brand,

        -- Pricing
        p.unit_price,
        p.cost_price,

        -- Margin: guard against zero unit_price to avoid division by zero
        CASE
            WHEN p.unit_price IS NULL OR p.unit_price = 0 THEN NULL
            ELSE ROUND((p.unit_price - p.cost_price) / p.unit_price * 100, 2)
        END                                                                           AS margin_pct,

        -- Physical attributes
        p.weight_kg,

        -- Inventory
        p.stock_quantity,
        p.reorder_level,

        -- Timestamps
        p.created_at,

        -- Audit
        current_timestamp                                                             AS dbt_updated_at

    FROM source_products AS p
    LEFT JOIN source_categories AS c
        ON p.category_id = c.category_id

    -- DQ filter: only active products in the catalog
    WHERE p.is_active = TRUE

)

SELECT *
FROM joined
