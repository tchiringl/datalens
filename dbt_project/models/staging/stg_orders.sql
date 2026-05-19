{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_orders
  ----------
  Cleans and deduplicates order data from the PostgreSQL source.
  Key transformations:
    - DEDUPLICATE on order_code — known DQ issue where the same business order_code
      can appear multiple times; we keep the row with the latest created_at
    - Derive order_month (truncated to first of month for grouping)
    - Derive order_year as integer
    - Derive is_online flag (store_id IS NULL means online order)
    - Retain all status values (no filtering)
*/

WITH source AS (

    SELECT *
    FROM {{ source('retail', 'orders') }}

),

-- Deduplicate: assign row number per order_code, ordered by latest created_at first
deduped AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_code
            ORDER BY created_at DESC
        ) AS rn

    FROM source

),

cleaned AS (

    SELECT
        -- Primary key
        order_id,

        -- Business key (deduplicated)
        TRIM(order_code)                                     AS order_code,

        -- Foreign keys
        customer_id,
        store_id,

        -- Dates
        CAST(order_date AS DATE)                             AS order_date,
        DATE_TRUNC('month', CAST(order_date AS DATE))        AS order_month,
        YEAR(CAST(order_date AS DATE))                       AS order_year,

        -- Derived flags
        CASE WHEN store_id IS NULL THEN TRUE ELSE FALSE END  AS is_online,

        -- Order financials
        subtotal,
        discount_amount,
        shipping_cost,
        tax_amount,
        total_amount,

        -- Payment and fulfillment
        TRIM(currency_code)                                  AS currency_code,
        TRIM(payment_method)                                 AS payment_method,
        TRIM(status)                                         AS order_status,

        -- Promotions
        TRIM(promo_code)                                     AS promo_code,

        -- Timestamps
        created_at,

        -- Audit
        current_timestamp                                    AS dbt_updated_at

    FROM deduped

    -- Keep only the canonical row per order_code
    WHERE rn = 1

)

SELECT *
FROM cleaned
