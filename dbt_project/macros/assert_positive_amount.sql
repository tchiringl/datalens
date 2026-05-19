/*
  test_assert_positive_amount
  ---------------------------
  Generic schema test macro that asserts all values in a given column are
  strictly non-negative (>= 0).  Any row where the column is negative will
  be returned, causing the test to fail.

  Usage in schema.yml:
    columns:
      - name: refund_amount
        tests:
          - assert_positive_amount

  The macro follows dbt's generic test convention:
    - Receives `model` (the relation) and `column_name` (the column to test)
    - Returns a SELECT of failing rows (empty = test passes)
*/

{% macro test_assert_positive_amount(model, column_name) %}

SELECT *
FROM {{ model }}
WHERE {{ column_name }} < 0

{% endmacro %}
