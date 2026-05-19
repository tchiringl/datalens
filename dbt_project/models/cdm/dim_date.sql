{{
    config(
        materialized = 'table',
        schema       = 'cdm'
    )
}}

/*
  dim_date
  --------
  CDM Date dimension table covering 2022-01-01 through 2025-12-31.
  Generated using Trino's sequence() function to produce all dates in range.

  Columns:
    - date_id        : integer YYYYMMDD surrogate key
    - date_actual    : the calendar DATE
    - day_of_week    : 1 = Sunday ... 7 = Saturday (Trino DOW_OF_WEEK is Mon=1)
    - day_name       : full name e.g. 'Monday'
    - day_of_month   : 1–31
    - day_of_year    : 1–366
    - week_of_year   : ISO week number
    - month_number   : 1–12
    - month_name     : full name e.g. 'January'
    - quarter        : 1–4
    - year           : four-digit year
    - is_weekend     : TRUE for Saturday and Sunday
    - is_weekday     : TRUE for Monday through Friday
*/

WITH date_spine AS (

    SELECT
        -- Trino sequence generates an array; UNNEST expands it to rows
        CAST(date_val AS DATE) AS date_actual
    FROM
        UNNEST(
            SEQUENCE(
                DATE '2022-01-01',
                DATE '2025-12-31',
                INTERVAL '1' DAY
            )
        ) AS t(date_val)

)

SELECT
    -- Surrogate key: integer YYYYMMDD
    CAST(
        CONCAT(
            CAST(YEAR(date_actual)  AS VARCHAR),
            LPAD(CAST(MONTH(date_actual) AS VARCHAR), 2, '0'),
            LPAD(CAST(DAY(date_actual)   AS VARCHAR), 2, '0')
        ) AS INTEGER
    )                                                              AS date_id,

    date_actual,

    -- Day of week: Trino DAY_OF_WEEK returns 1=Monday … 7=Sunday
    -- Convert to 1=Sunday … 7=Saturday for common BI convention
    CASE DAY_OF_WEEK(date_actual)
        WHEN 7 THEN 1   -- Sunday
        WHEN 1 THEN 2   -- Monday
        WHEN 2 THEN 3   -- Tuesday
        WHEN 3 THEN 4   -- Wednesday
        WHEN 4 THEN 5   -- Thursday
        WHEN 5 THEN 6   -- Friday
        WHEN 6 THEN 7   -- Saturday
    END                                                            AS day_of_week,

    -- Day name
    DATE_FORMAT(date_actual, '%W')                                 AS day_name,

    -- Day of month (1–31)
    DAY(date_actual)                                               AS day_of_month,

    -- Day of year (1–366)
    DAY_OF_YEAR(date_actual)                                       AS day_of_year,

    -- ISO week of year
    WEEK(date_actual)                                              AS week_of_year,

    -- Month
    MONTH(date_actual)                                             AS month_number,
    DATE_FORMAT(date_actual, '%M')                                 AS month_name,

    -- Quarter
    QUARTER(date_actual)                                           AS quarter,

    -- Year
    YEAR(date_actual)                                              AS year,

    -- Weekend / weekday flags
    -- Trino DAY_OF_WEEK: 6=Saturday, 7=Sunday
    CASE
        WHEN DAY_OF_WEEK(date_actual) IN (6, 7) THEN TRUE
        ELSE FALSE
    END                                                            AS is_weekend,

    CASE
        WHEN DAY_OF_WEEK(date_actual) IN (6, 7) THEN FALSE
        ELSE TRUE
    END                                                            AS is_weekday

FROM date_spine

ORDER BY date_actual
