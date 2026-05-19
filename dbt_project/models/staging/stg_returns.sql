{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_returns
  -----------
  Cleans and enriches returns data.
  Key transformations:
    - Join to stg_orders to resolve order_code and order_date context
    - Join to order_items + stg_products to resolve product_sku
    - Standardize reason and status string fields
    - Cast return_date to DATE
*/

WITH source_returns AS (

    SELECT *
    FROM {{ source('retail', 'returns') }}

),

stg_orders AS (

    SELECT
        order_id,
        order_code,
        order_date,
        customer_id
    FROM {{ ref('stg_orders') }}

),

source_order_items AS (

    SELECT
        order_item_id,
        product_id
    FROM {{ source('retail', 'order_items') }}

),

source_products AS (

    SELECT
        product_id,
        sku
    FROM {{ source('retail', 'products') }}

),

joined AS (

    SELECT
        -- Primary key
        r.return_id,

        -- Foreign keys
        r.order_id,
        r.order_item_id,

        -- Enriched from orders
        o.order_code,
        o.customer_id,
        o.order_date,

        -- Enriched from order_items + products
        p.product_id,
        p.sku                                    AS product_sku,

        -- Return details
        CAST(r.return_date AS DATE)              AS return_date,
        TRIM(r.reason)                           AS reason,
        TRIM(r.status)                           AS return_status,
        r.refund_amount,

        -- Audit
        current_timestamp                        AS dbt_updated_at

    FROM source_returns AS r
    LEFT JOIN stg_orders AS o
        ON r.order_id = o.order_id
    LEFT JOIN source_order_items AS oi
        ON r.order_item_id = oi.order_item_id
    LEFT JOIN source_products AS p
        ON oi.product_id = p.product_id

)

SELECT *
FROM joined
