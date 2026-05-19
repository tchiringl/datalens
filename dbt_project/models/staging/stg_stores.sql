{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_stores
  ----------
  Cleans and enriches store data.
  Key transformations:
    - Join to countries to get country_name and region
    - Standardize store_type to UPPER for consistent filtering
    - Derive store_age_years from opened_date to today
*/

WITH source_stores AS (

    SELECT *
    FROM {{ source('retail', 'stores') }}

),

source_countries AS (

    SELECT *
    FROM {{ source('retail', 'countries') }}

),

joined AS (

    SELECT
        -- Primary key
        s.store_id,

        -- Business key
        TRIM(s.store_code)                                                              AS store_code,

        -- Store details
        TRIM(s.store_name)                                                              AS store_name,
        UPPER(TRIM(s.store_type))                                                       AS store_type,

        -- Geography
        TRIM(s.city)                                                                    AS city,
        TRIM(s.state_province)                                                          AS state_province,
        s.country_id,
        TRIM(c.country_name)                                                            AS country_name,
        TRIM(c.region)                                                                  AS region,
        TRIM(s.zip_code)                                                                AS zip_code,

        -- Store lifecycle
        CAST(s.opened_date AS DATE)                                                     AS opened_date,

        -- store_age_years: whole years from opening to today using day difference
        FLOOR(
            DATE_DIFF('day', CAST(s.opened_date AS DATE), CURRENT_DATE) / 365.25
        )                                                                               AS store_age_years,

        -- Physical attributes
        s.square_footage,

        -- Status
        s.is_active,

        -- Personnel
        TRIM(s.manager_name)                                                            AS manager_name,

        -- Audit
        current_timestamp                                                               AS dbt_updated_at

    FROM source_stores AS s
    LEFT JOIN source_countries AS c
        ON s.country_id = c.country_id

)

SELECT *
FROM joined
