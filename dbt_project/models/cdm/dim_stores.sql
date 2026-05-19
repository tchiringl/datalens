{{
    config(
        materialized = 'table',
        schema       = 'cdm'
    )
}}

/*
  dim_stores
  ----------
  CDM Store dimension table.
  Grain: one row per store.
  Materialized as a full table (small reference dimension, no incremental needed).

  All enrichment (country_name, region, store_age_years) is sourced from stg_stores
  which already joined to the countries reference table.
*/

WITH stg_stores AS (

    SELECT *
    FROM {{ ref('stg_stores') }}

)

SELECT
    -- Primary key
    store_id,

    -- Business key
    store_code,

    -- Store identity
    store_name,
    store_type,

    -- Geography
    city,
    state_province,
    country_id,
    country_name,
    region,
    zip_code,

    -- Lifecycle
    opened_date,
    store_age_years,

    -- Physical attributes
    square_footage,

    -- Status
    is_active,

    -- Personnel
    manager_name,

    -- Audit
    dbt_updated_at

FROM stg_stores
