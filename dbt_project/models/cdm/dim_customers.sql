{{
    config(
        materialized  = 'incremental',
        schema        = 'cdm',
        unique_key    = 'customer_id',
        on_schema_change = 'append_new_columns'
    )
}}

/*
  dim_customers
  -------------
  CDM Customer dimension table.
  Grain: one row per active customer.

  Incremental strategy:
    - On full refresh: loads all active customers from stg_customers
    - On incremental run: loads only customers whose created_at is after the
      current max created_date in the target table, then MERGE/upsert on customer_id

  Derived columns:
    - age_years: calculated from date_of_birth to today
    - customer_segment: derived business segment from loyalty_tier
*/

WITH stg_customers AS (

    SELECT *
    FROM {{ ref('stg_customers') }}

    {% if is_incremental() %}
    -- Only load records newer than the latest created_date already in the table
    WHERE created_date > (SELECT MAX(created_date) FROM {{ this }})
    {% endif %}

),

source_countries AS (

    SELECT
        country_id,
        TRIM(country_name) AS country_name,
        TRIM(region)       AS region
    FROM {{ source('retail', 'countries') }}

),

enriched AS (

    SELECT
        -- Primary key
        c.customer_id,

        -- Business key
        c.customer_code,

        -- Full name (concatenated)
        TRIM(CONCAT(c.first_name, ' ', c.last_name))                             AS full_name,

        -- Email (cleaned in staging layer)
        c.email_cleaned                                                           AS email,
        c.has_email,

        -- Contact
        c.phone,

        -- Demographics
        c.date_of_birth,

        -- age_years: floor of days since DOB divided by 365.25
        CASE
            WHEN c.date_of_birth IS NOT NULL
            THEN CAST(
                FLOOR(DATE_DIFF('day', c.date_of_birth, CURRENT_DATE) / 365.25)
                AS INTEGER
            )
            ELSE NULL
        END                                                                       AS age_years,

        c.gender,

        -- Geography
        c.city,
        c.state_province,
        c.country_id,
        co.country_name,
        co.region,
        c.zip_code,

        -- Loyalty
        c.loyalty_tier,
        c.loyalty_points,

        -- Acquisition
        c.acquired_channel,

        -- Derived business segment from loyalty tier
        CASE
            WHEN c.loyalty_tier = 'PLATINUM' THEN 'VIP'
            WHEN c.loyalty_tier = 'GOLD'     THEN 'High Value'
            WHEN c.loyalty_tier = 'SILVER'   THEN 'Regular'
            WHEN c.loyalty_tier = 'BRONZE'   THEN 'New'
            ELSE 'Unknown'
        END                                                                       AS customer_segment,

        -- Dates
        c.created_date,

        -- Audit
        c.dbt_updated_at

    FROM stg_customers AS c
    LEFT JOIN source_countries AS co
        ON c.country_id = co.country_id

)

SELECT *
FROM enriched
