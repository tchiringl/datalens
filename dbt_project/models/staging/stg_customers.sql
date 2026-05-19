{{
    config(
        materialized = 'table',
        schema = 'staging'
    )
}}

/*
  stg_customers
  -------------
  Cleans and standardizes raw customer data from the PostgreSQL source.
  Key transformations:
    - TRIM all string fields to remove leading/trailing whitespace
    - UPPER loyalty_tier for consistency
    - COALESCE email to a placeholder where NULL (known DQ issue)
    - Add has_email flag to identify customers with real email addresses
    - Cast created_at to DATE
    - Filter out inactive customers (is_active = FALSE)
    - Stamp dbt_updated_at for lineage tracking
*/

WITH source AS (

    SELECT *
    FROM {{ source('retail', 'customers') }}

),

cleaned AS (

    SELECT
        -- Primary key
        customer_id,

        -- Business key
        TRIM(customer_code)                                                         AS customer_code,

        -- Name fields
        TRIM(first_name)                                                            AS first_name,
        TRIM(last_name)                                                             AS last_name,

        -- Email: coalesce NULL emails, add presence flag
        COALESCE(TRIM(email), 'unknown@noemail.com')                               AS email_cleaned,
        CASE WHEN email IS NOT NULL AND TRIM(email) <> '' THEN TRUE ELSE FALSE END AS has_email,

        -- Phone
        TRIM(phone)                                                                 AS phone,

        -- Demographics
        CAST(date_of_birth AS DATE)                                                 AS date_of_birth,
        TRIM(gender)                                                                AS gender,

        -- Geography
        TRIM(city)                                                                  AS city,
        TRIM(state_province)                                                        AS state_province,
        country_id,
        TRIM(zip_code)                                                              AS zip_code,

        -- Loyalty: standardize tier to UPPER for consistent matching
        UPPER(TRIM(loyalty_tier))                                                   AS loyalty_tier,
        loyalty_points,

        -- Acquisition
        TRIM(acquired_channel)                                                      AS acquired_channel,

        -- Timestamps
        CAST(created_at AS DATE)                                                    AS created_date,

        -- Audit
        current_timestamp                                                           AS dbt_updated_at

    FROM source

    -- DQ filter: exclude inactive customer accounts
    WHERE is_active = TRUE

)

SELECT *
FROM cleaned
