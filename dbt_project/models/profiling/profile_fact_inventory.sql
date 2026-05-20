{{
    config(
        materialized = 'table',
        schema       = 'profiling'
    )
}}

SELECT
    COUNT(*)                                                                                                  AS total_snapshots,
    COUNT(DISTINCT product_id)                                                                                AS distinct_products,
    COUNT(DISTINCT store_id)                                                                                  AS distinct_stores,
    SUM(CASE WHEN quantity_on_hand = 0 THEN 1 ELSE 0 END)                                                    AS zero_stock_count,
    ROUND(100.0 * SUM(CASE WHEN quantity_on_hand = 0 THEN 1 ELSE 0 END) / COUNT(*), 2)                       AS zero_stock_pct,
    ROUND(100.0 * SUM(CASE WHEN available_quantity < 0 THEN 1 ELSE 0 END) / COUNT(*), 2)                     AS negative_available_pct,
    ROUND(AVG(CAST(quantity_on_hand AS DOUBLE)), 2)                                                           AS avg_stock_on_hand,
    MAX(snapshot_date)                                                                                        AS latest_snapshot
FROM {{ ref('fact_inventory') }}
