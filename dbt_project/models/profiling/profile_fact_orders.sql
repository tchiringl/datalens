{{
    config(
        materialized = 'table',
        schema       = 'profiling'
    )
}}

SELECT
    COUNT(*)                                                                          AS total_rows,
    COUNT(DISTINCT customer_id)                                                       AS distinct_customers,
    COUNT(DISTINCT order_id)                                                          AS distinct_orders,
    COUNT(DISTINCT product_id)                                                        AS distinct_products,
    ROUND(100.0 * SUM(CASE WHEN store_id IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)   AS store_id_null_pct,
    ROUND(100.0 * SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS customer_id_null_pct,
    MIN(order_date)                                                                   AS min_order_date,
    MAX(order_date)                                                                   AS max_order_date,
    ROUND(AVG(CAST(line_total_fixed AS DOUBLE)), 2)                                   AS avg_line_total,
    ROUND(MIN(CAST(line_total_fixed AS DOUBLE)), 2)                                   AS min_line_total,
    ROUND(MAX(CAST(line_total_fixed AS DOUBLE)), 2)                                   AS max_line_total,
    ROUND(APPROX_PERCENTILE(CAST(line_total_fixed AS DOUBLE), 0.95), 2)               AS p95_line_total,
    MIN(quantity)                                                                     AS min_quantity,
    MAX(quantity)                                                                     AS max_quantity,
    ROUND(AVG(CAST(quantity AS DOUBLE)), 2)                                           AS avg_quantity
FROM {{ ref('fact_orders') }}
