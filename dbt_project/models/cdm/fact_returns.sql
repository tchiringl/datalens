{{
    config(
        materialized  = 'incremental',
        schema        = 'cdm',
        unique_key    = 'return_id',
        on_schema_change = 'append_new_columns'
    )
}}

/*
  fact_returns
  ------------
  Returns fact table.
  Grain: one row per return transaction.

  Joins:
    stg_returns   → clean return records with product_sku and order_code
    fact_orders   → full order context (customer_id, product_id, order_date)

  Incremental strategy:
    Load returns whose return_date is later than the latest return_date
    already present in the fact table.

  Derived columns:
    - days_to_return: number of days between order_date and return_date,
      useful for return window analysis
*/

WITH stg_returns AS (

    SELECT *
    FROM {{ ref('stg_returns') }}

    {% if is_incremental() %}
    WHERE return_date > (SELECT MAX(return_date) FROM {{ this }})
    {% endif %}

),

fact_orders AS (

    SELECT
        order_id,
        order_item_id,
        customer_id,
        product_id,
        order_date
    FROM {{ ref('fact_orders') }}

),

joined AS (

    SELECT
        -- Primary key
        r.return_id,

        -- Foreign keys
        r.order_id,
        r.order_item_id,

        -- Customer context (from fact_orders)
        fo.customer_id,

        -- Product context (from fact_orders)
        fo.product_id,

        -- Return timing
        r.return_date,
        fo.order_date,

        -- Derived: number of days between order and return
        DATE_DIFF('day', fo.order_date, r.return_date)   AS days_to_return,

        -- Return details
        r.reason,
        r.return_status                                   AS status,
        r.refund_amount,

        -- Audit
        current_timestamp                                 AS dbt_updated_at

    FROM stg_returns AS r
    LEFT JOIN fact_orders AS fo
        ON r.order_item_id = fo.order_item_id

)

SELECT *
FROM joined
