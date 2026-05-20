{{
    config(
        materialized = 'table',
        schema       = 'profiling'
    )
}}

SELECT
    COUNT(*)                                                                                     AS total_customers,
    COUNT(DISTINCT loyalty_tier)                                                                 AS distinct_loyalty_tiers,
    COUNT(DISTINCT customer_segment)                                                             AS distinct_segments,
    ROUND(100.0 * SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)                 AS email_null_pct,
    ROUND(100.0 * SUM(CASE WHEN phone IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)                 AS phone_null_pct,
    ROUND(100.0 * SUM(CASE WHEN customer_segment = 'Unknown' THEN 1 ELSE 0 END) / COUNT(*), 2)  AS unknown_segment_pct,
    MIN(created_date)                                                                            AS earliest_customer,
    MAX(created_date)                                                                            AS latest_customer
FROM {{ ref('dim_customers') }}
