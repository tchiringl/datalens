{{
    config(
        materialized = 'table',
        schema       = 'profiling'
    )
}}

SELECT
    COUNT(*)                                                                                                          AS total_returns,
    ROUND(
        100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM {{ ref('fact_orders') }}), 0),
        2
    )                                                                                                                 AS return_rate_pct,
    ROUND(AVG(CAST(refund_amount AS DOUBLE)), 2)                                                                      AS avg_refund,
    ROUND(MIN(CAST(refund_amount AS DOUBLE)), 2)                                                                      AS min_refund,
    ROUND(MAX(CAST(refund_amount AS DOUBLE)), 2)                                                                      AS max_refund,
    MIN(return_date)                                                                                                  AS earliest_return,
    MAX(return_date)                                                                                                  AS latest_return,
    COUNT(DISTINCT order_id)                                                                                          AS distinct_orders_with_returns
FROM {{ ref('fact_returns') }}
