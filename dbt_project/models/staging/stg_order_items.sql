{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_order_items
  ---------------
  Cleans order line-item data.
  Key transformations:
    - Fix line_total: when zero or NULL (known DQ issue), recalculate from
      quantity * unit_price * (1 - discount_pct / 100)
    - Add had_line_total_issue flag to preserve knowledge of the DQ event
    - Join to stg_orders to enrich items with order_date for downstream use
*/

WITH source_items AS (

    SELECT *
    FROM {{ source('retail', 'order_items') }}

),

stg_orders AS (

    SELECT
        order_id,
        order_date
    FROM {{ ref('stg_orders') }}

),

cleaned AS (

    SELECT
        -- Primary key
        oi.order_item_id,

        -- Foreign keys
        oi.order_id,
        oi.product_id,

        -- Order date (enriched from stg_orders)
        o.order_date,

        -- Quantity
        oi.quantity,

        -- Pricing at time of order
        oi.unit_price,
        oi.discount_pct,

        -- line_total fix:
        --   If line_total is 0 or NULL (DQ issue), derive from quantity and price.
        --   NULLIF converts 0 -> NULL so COALESCE can substitute the calculation.
        COALESCE(
            NULLIF(oi.line_total, 0),
            oi.quantity * oi.unit_price * (1.0 - COALESCE(oi.discount_pct, 0) / 100.0)
        )                                                            AS line_total_fixed,

        -- DQ flag: mark rows where the original value was suspect
        CASE
            WHEN oi.line_total = 0 OR oi.line_total IS NULL THEN TRUE
            ELSE FALSE
        END                                                          AS had_line_total_issue,

        -- Audit
        current_timestamp                                            AS dbt_updated_at

    FROM source_items AS oi
    LEFT JOIN stg_orders AS o
        ON oi.order_id = o.order_id

)

SELECT *
FROM cleaned
