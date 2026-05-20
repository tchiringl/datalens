{% test alert_high_null_rate(model, column_name, threshold=0.05) %}
    SELECT COUNT(*) AS failing_rows
    FROM {{ model }}
    WHERE {{ column_name }} IS NULL
    HAVING COUNT(*) > (SELECT COUNT(*) * {{ threshold }} FROM {{ model }})
{% endtest %}
