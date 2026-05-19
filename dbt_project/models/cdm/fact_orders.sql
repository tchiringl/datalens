{{
    config(
        materialized  = 'incremental',
        schema        = 'cdm',
        unique_key    = 'order_item_id',
        on_schema_change = 'append_new_columns'
    )
}}

/*
  fact_orders
  -----------
  Core transactional fact table.
  Grain: one row per order line item (order_id + order_item_id).

  Joins:
    stg_orders      → order header attributes
    stg_order_items → line-item detail (quantity, pricing, DQ flags)
    dim_customers   → customer context (segment, code)
    dim_products    → product context (name, category, brand)
    dim_stores      → store context (name, type, country)

  Incremental strategy:
    Load order items whose order_date is later than the latest order_date
    already present in the fact table.

  Note: store_id can be NULL for online orders (is_online = TRUE),
        so dim_stores join is a LEFT JOIN.
*/

WITH stg_orders AS (

    SELECT *
    FROM {{ ref('stg_orders') }}

    {% if is_incremental() %}
    WHERE order_date > (SELECT MAX(order_date) FROM {{ this }})
    {% endif %}

),

stg_order_items AS (

    SELECT *
    FROM {{ ref('stg_order_items') }}

),

dim_customers AS (

    SELECT
        customer_id,
        customer_code,
        customer_segment
    FROM {{ ref('dim_customers') }}

),

dim_products AS (

    SELECT
        product_id,
        sku,
        product_name,
        category_name,
        brand
    FROM {{ ref('dim_products') }}

),

dim_stores AS (

    SELECT
        store_id,
        store_name,
        store_type,
        country_id
    FROM {{ ref('dim_stores') }}

),

joined AS (

    SELECT
        -- Surrogate PK for the fact row
        oi.order_item_id,

        -- Order header keys
        o.order_id,
        o.order_code,

        -- Customer context
        o.customer_id,
        c.customer_code,
        c.customer_segment,

        -- Store context (NULL for online orders)
        o.store_id,
        s.store_name,
        s.store_type,
        s.country_id,

        -- Product context
        oi.product_id,
        p.sku,
        p.product_name,
        p.category_name,
        p.brand,

        -- Order dates
        o.order_date,
        o.order_month,
        o.order_year,

        -- Line item metrics
        oi.quantity,
        oi.unit_price,
        oi.discount_pct,
        oi.line_total_fixed,

        -- Order-level financials (from order header)
        o.subtotal,
        o.discount_amount,
        o.shipping_cost,
        o.tax_amount,
        o.total_amount,

        -- Order metadata
        o.currency_code,
        o.payment_method,
        o.order_status,
        o.is_online,
        o.promo_code,

        -- Data quality flag from staging
        oi.had_line_total_issue,

        -- Audit
        current_timestamp AS dbt_updated_at

    FROM stg_orders AS o
    INNER JOIN stg_order_items AS oi
        ON o.order_id = oi.order_id
    LEFT JOIN dim_customers AS c
        ON o.customer_id = c.customer_id
    LEFT JOIN dim_products AS p
        ON oi.product_id = p.product_id
    LEFT JOIN dim_stores AS s
        ON o.store_id = s.store_id

)

SELECT *
FROM joined
