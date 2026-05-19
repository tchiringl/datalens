/*
  assert_order_total_valid
  ------------------------
  Singular data test for fact_orders.

  Assertion:
    total_amount must be >= (subtotal - discount_amount) for every order row.

  Rationale:
    The order total is built as: subtotal - discount_amount + shipping_cost + tax_amount.
    Therefore total_amount should NEVER be less than (subtotal - discount_amount),
    because shipping and tax are always non-negative additions.

    Any row violating this condition indicates a data integrity issue in the
    source order financials (e.g. a miscalculated total or corrupted record).

  Rows returned = test failures.
  An empty result set means the test passes.
*/

SELECT *
FROM {{ ref('fact_orders') }}
WHERE total_amount < (subtotal - discount_amount)
  AND total_amount IS NOT NULL
  AND subtotal     IS NOT NULL
