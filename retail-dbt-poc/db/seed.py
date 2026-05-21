import argparse
import os
import random
import string
from datetime import datetime, timedelta, date
import psycopg2
from psycopg2.extras import execute_batch
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

BATCH_SIZE = 500


def random_alphanum(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


def random_date_in_past(days=730):
    return datetime.now() - timedelta(days=random.randint(0, days))


def parse_args():
    parser = argparse.ArgumentParser(description="Seed the retail PostgreSQL database")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5435)
    parser.add_argument("--user", default="retail")
    parser.add_argument("--password", default="retail123")
    parser.add_argument("--dbname", default="retail")
    return parser.parse_args()


def get_conn(args):
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname,
    )
    conn.autocommit = False
    return conn


# ---------------------------------------------------------------------------
# 1. stores (50 rows)
# ---------------------------------------------------------------------------
def seed_stores(cur):
    print("Seeding stores... 50 rows")
    store_types = ['flagship', 'retail', 'outlet', 'online']
    rows = []
    for _ in range(50):
        rows.append((
            fake.company(),
            random.choice(store_types),
            fake.city(),
            fake.country()[:100],
            fake.state()[:100],
            fake.phone_number()[:30],
            fake.company_email(),
            fake.date_between(start_date='-10y', end_date='-1y'),
            True,
        ))
    execute_batch(
        cur,
        """INSERT INTO stores (name, store_type, city, country, region, phone, email, opened_at, is_active)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 2. product_categories (20 rows)
# ---------------------------------------------------------------------------
def seed_product_categories(cur):
    print("Seeding product_categories... 20 rows")
    # First 5: parent categories (parent_category_id = NULL)
    parent_rows = []
    for _ in range(5):
        parent_rows.append((
            fake.unique.word().capitalize() + " " + fake.word().capitalize(),
            None,
            fake.sentence(),
        ))
    execute_batch(
        cur,
        """INSERT INTO product_categories (name, parent_category_id, description)
           VALUES (%s, %s, %s)""",
        parent_rows,
        page_size=BATCH_SIZE,
    )

    # Remaining 15: reference one of the 5 parents (IDs 1-5)
    child_rows = []
    for _ in range(15):
        child_rows.append((
            fake.unique.word().capitalize() + " " + fake.word().capitalize(),
            random.randint(1, 5),
            fake.sentence(),
        ))
    execute_batch(
        cur,
        """INSERT INTO product_categories (name, parent_category_id, description)
           VALUES (%s, %s, %s)""",
        child_rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 3. suppliers (100 rows)
# ---------------------------------------------------------------------------
def seed_suppliers(cur):
    print("Seeding suppliers... 100 rows")
    rows = []
    for _ in range(100):
        rows.append((
            fake.company(),
            fake.name(),
            fake.company_email(),
            fake.phone_number()[:30],
            fake.country()[:100],
            True,
        ))
    execute_batch(
        cur,
        """INSERT INTO suppliers (name, contact_name, email, phone, country, is_active)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 4. products (500 rows)
# ---------------------------------------------------------------------------
def seed_products(cur):
    print("Seeding products... 500 rows")
    rows = []
    for i in range(1, 501):
        unit_price = round(random.uniform(10.0, 500.0), 2)
        # IDs 481-500 (i == 481..500): cost_price = NULL
        if i >= 481:
            cost_price = None
        else:
            cost_price = round(unit_price * random.uniform(0.5, 0.8), 2)
        sku = 'SKU-' + random_alphanum(8)
        rows.append((
            fake.catch_phrase()[:200],
            sku,
            random.randint(1, 20),
            random.randint(1, 100),
            unit_price,
            cost_price,
            random.randint(0, 1000),
            True,
        ))
    execute_batch(
        cur,
        """INSERT INTO products (name, sku, category_id, supplier_id, unit_price, cost_price, stock_quantity, is_active)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 5. customers (5000 rows)
# ---------------------------------------------------------------------------
def seed_customers(cur):
    print("Seeding customers... 5000 rows")
    tiers = ['standard', 'silver', 'gold', 'platinum']
    rows = []
    for i in range(1, 5001):
        # Rows 4801-5000: email = NULL
        if i >= 4801:
            email = None
        else:
            email = fake.unique.email()

        # Rows 4951-5000: created_at = future date (NOW + 1-365 days)
        if i >= 4951:
            created_at = datetime.now() + timedelta(days=random.randint(1, 365))
        else:
            created_at = random_date_in_past(days=1825)

        rows.append((
            fake.first_name(),
            fake.last_name(),
            email,
            fake.phone_number()[:30],
            random.choice(tiers),
            created_at,
            True,
        ))
    execute_batch(
        cur,
        """INSERT INTO customers (first_name, last_name, email, phone, loyalty_tier, created_at, is_active)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 6. promotions (100 rows)
# ---------------------------------------------------------------------------
def seed_promotions(cur):
    print("Seeding promotions... 100 rows")
    rows = []
    for i in range(100):
        code = 'PROMO' + random_alphanum(6)
        discount_type = 'percentage' if i % 2 == 0 else 'fixed'
        discount_value = round(random.uniform(5.0, 50.0), 2)
        starts_at = random_date_in_past(days=365)
        ends_at = starts_at + timedelta(days=random.randint(7, 90))
        rows.append((
            code,
            discount_type,
            discount_value,
            starts_at,
            ends_at,
            True,
        ))
    execute_batch(
        cur,
        """INSERT INTO promotions (code, discount_type, discount_value, starts_at, ends_at, is_active)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 7. employees (200 rows)
# ---------------------------------------------------------------------------
def seed_employees(cur):
    print("Seeding employees... 200 rows")
    roles = ['manager', 'associate', 'cashier', 'stock', 'analyst']
    rows = []
    for i in range(1, 201):
        # First 10 are managers with no manager_id
        if i <= 10:
            role = 'manager'
            manager_id = None
        else:
            role = random.choice(roles)
            manager_id = random.randint(1, 10)
        rows.append((
            random.randint(1, 50),
            fake.first_name(),
            fake.last_name(),
            role,
            round(random.uniform(30000, 120000), 2),
            fake.date_between(start_date='-8y', end_date='-1m'),
            manager_id,
        ))
    execute_batch(
        cur,
        """INSERT INTO employees (store_id, first_name, last_name, role, salary, hire_date, manager_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 8. orders (20000 rows)
# ---------------------------------------------------------------------------
def seed_orders(cur):
    print("Seeding orders... 20000 rows")
    statuses = ['pending', 'completed', 'completed', 'completed', 'cancelled', 'refunded']
    rows = []
    for i in range(1, 20001):
        # Duplicate order codes for orders 1-500:
        # orders 1&2 share 'ORD-DUP-001', 3&4 share 'ORD-DUP-002', etc.
        if i <= 500:
            dup_num = (i + 1) // 2  # 1->1, 2->1, 3->2, 4->2, ...
            order_code = f'ORD-DUP-{dup_num:03d}'
        else:
            order_code = f'ORD-{i:06d}'

        customer_id = random.randint(1, 5000)
        store_id = random.randint(1, 50)
        promotion_id = random.randint(1, 100) if random.random() < 0.2 else None
        subtotal = round(random.uniform(20.0, 2000.0), 2)
        discount_amount = round(subtotal * random.uniform(0, 0.3), 2) if promotion_id else 0.0
        total_amount = round(subtotal - discount_amount, 2)

        # Orders 19951-20000: negative total_amount
        if i >= 19951:
            total_amount = -1 * abs(total_amount)

        status = random.choice(statuses)
        ordered_at = random_date_in_past(days=730)
        updated_at = ordered_at + timedelta(hours=random.randint(0, 72))

        rows.append((
            order_code,
            customer_id,
            store_id,
            promotion_id,
            subtotal,
            discount_amount,
            total_amount,
            status,
            ordered_at,
            updated_at,
        ))
    execute_batch(
        cur,
        """INSERT INTO orders (order_code, customer_id, store_id, promotion_id, subtotal, discount_amount,
                               total_amount, status, ordered_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 9. order_items (~60000 rows, ~3 per order)
# ---------------------------------------------------------------------------
def seed_order_items(cur):
    print("Seeding order_items... ~60000 rows")
    rows = []
    item_index = 0

    # Pre-determine which items get special DQ treatment.
    # We don't know exact item indices ahead of time, so we track count and
    # mark first 300 for zero line_total and next 100 for negative quantity.
    zero_line_total_count = 0
    neg_qty_count = 0
    zero_line_total_limit = 300
    neg_qty_limit = 100

    for order_id in range(1, 20001):
        num_items = random.randint(1, 5)
        for _ in range(num_items):
            item_index += 1
            product_id = random.randint(1, 500)
            unit_price = round(random.uniform(5.0, 500.0), 2)
            quantity = random.randint(1, 10)

            if zero_line_total_count < zero_line_total_limit:
                line_total = 0.00
                zero_line_total_count += 1
            elif neg_qty_count < neg_qty_limit:
                quantity = -1 * abs(quantity)
                line_total = round(quantity * unit_price, 2)
                neg_qty_count += 1
            else:
                line_total = round(quantity * unit_price, 2)

            rows.append((order_id, product_id, quantity, unit_price, line_total))

    print(f"  (actual order_items rows: {len(rows)})")
    execute_batch(
        cur,
        """INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
           VALUES (%s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 10. returns (3000 rows)
# ---------------------------------------------------------------------------
def seed_returns(cur):
    print("Seeding returns... 3000 rows")
    statuses = ['pending', 'approved', 'rejected', 'processed']
    reasons = [
        "Defective product", "Wrong item", "Changed mind",
        "Not as described", "Damaged in transit", "Duplicate order",
    ]
    rows = []
    for _ in range(3000):
        order_id = random.randint(1, 20000)
        # We need the customer for that order; we stored orders in memory
        # so just pick a consistent customer_id from the same range
        customer_id = random.randint(1, 5000)
        rows.append((
            order_id,
            customer_id,
            random.choice(reasons),
            round(random.uniform(5.0, 500.0), 2),
            random.choice(statuses),
            random_date_in_past(days=365),
        ))
    execute_batch(
        cur,
        """INSERT INTO returns (order_id, customer_id, reason, amount, status, created_at)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 11. shipments (18000 rows, one per order for orders 1-18000)
# ---------------------------------------------------------------------------
def seed_shipments(cur):
    print("Seeding shipments... 18000 rows")
    carriers = ['FedEx', 'UPS', 'DHL', 'USPS', 'OnTrac']
    valid_statuses = ['pending', 'processing', 'shipped', 'delivered']
    invalid_statuses = ['unknown', 'lost']
    rows = []
    for order_id in range(1, 18001):
        # Last 50 (orders 17951-18000): invalid status
        if order_id >= 17951:
            status = random.choice(invalid_statuses)
        else:
            status = random.choice(valid_statuses)

        shipped_at = random_date_in_past(days=700) if status in ('shipped', 'delivered') else None
        delivered_at = (shipped_at + timedelta(days=random.randint(1, 10))
                        if status == 'delivered' and shipped_at else None)

        rows.append((
            order_id,
            random.choice(carriers),
            fake.bothify(text='??##########'),
            status,
            shipped_at,
            delivered_at,
        ))
    execute_batch(
        cur,
        """INSERT INTO shipments (order_id, carrier, tracking_number, status, shipped_at, delivered_at)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 12. product_reviews (8000 rows)
# ---------------------------------------------------------------------------
def seed_product_reviews(cur):
    print("Seeding product_reviews... 8000 rows")
    rows = []
    null_body_indices = set(random.sample(range(8000), 500))
    bad_rating_indices = set(random.sample(range(8000), 20))

    for i in range(8000):
        if i in bad_rating_indices:
            rating = random.choice([0, 6])
        else:
            rating = random.randint(1, 5)

        body = None if i in null_body_indices else fake.sentence()

        rows.append((
            random.randint(1, 500),
            random.randint(1, 5000),
            rating,
            fake.sentence()[:200],
            body,
            random_date_in_past(days=730),
        ))
    execute_batch(
        cur,
        """INSERT INTO product_reviews (product_id, customer_id, rating, title, body, created_at)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 13. loyalty_points (5000 rows, one per customer)
# ---------------------------------------------------------------------------
def seed_loyalty_points(cur):
    print("Seeding loyalty_points... 5000 rows")
    zero_balance_indices = set(random.sample(range(5000), 500))
    rows = []
    for i in range(5000):
        customer_id = i + 1
        if i in zero_balance_indices:
            balance = 0
            total_earned = 0
            total_redeemed = 0
        else:
            total_earned = random.randint(100, 10000)
            total_redeemed = random.randint(0, total_earned)
            balance = total_earned - total_redeemed

        rows.append((
            customer_id,
            balance,
            total_earned,
            total_redeemed,
            datetime.now(),
        ))
    execute_batch(
        cur,
        """INSERT INTO loyalty_points (customer_id, balance, total_earned, total_redeemed, updated_at)
           VALUES (%s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# 14. inventory_snapshots (10000 rows)
# ---------------------------------------------------------------------------
def seed_inventory_snapshots(cur):
    print("Seeding inventory_snapshots... 10000 rows")
    rows = []
    today = date.today()
    for _ in range(10000):
        snapshot_date = today - timedelta(days=random.randint(0, 90))
        rows.append((
            random.randint(1, 500),
            random.randint(1, 50),
            random.randint(0, 1000),
            random.randint(0, 200),
            snapshot_date,
        ))
    execute_batch(
        cur,
        """INSERT INTO inventory_snapshots (product_id, store_id, quantity_on_hand, quantity_reserved, snapshot_date)
           VALUES (%s, %s, %s, %s, %s)""",
        rows,
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def apply_schema(conn):
    """Drop all tables then recreate from schema.sql (idempotent reset)."""
    drop_sql = """
    DROP TABLE IF EXISTS inventory_snapshots CASCADE;
    DROP TABLE IF EXISTS loyalty_points CASCADE;
    DROP TABLE IF EXISTS product_reviews CASCADE;
    DROP TABLE IF EXISTS shipments CASCADE;
    DROP TABLE IF EXISTS returns CASCADE;
    DROP TABLE IF EXISTS order_items CASCADE;
    DROP TABLE IF EXISTS orders CASCADE;
    DROP TABLE IF EXISTS employees CASCADE;
    DROP TABLE IF EXISTS promotions CASCADE;
    DROP TABLE IF EXISTS customers CASCADE;
    DROP TABLE IF EXISTS products CASCADE;
    DROP TABLE IF EXISTS suppliers CASCADE;
    DROP TABLE IF EXISTS product_categories CASCADE;
    DROP TABLE IF EXISTS stores CASCADE;
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        create_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(drop_sql)
        cur.execute(create_sql)
    conn.commit()
    print("Schema applied.")


def main():
    args = parse_args()
    conn = get_conn(args)
    cur = conn.cursor()

    apply_schema(conn)

    try:
        seed_stores(cur)
        conn.commit()

        seed_product_categories(cur)
        conn.commit()

        seed_suppliers(cur)
        conn.commit()

        seed_products(cur)
        conn.commit()

        seed_customers(cur)
        conn.commit()

        seed_promotions(cur)
        conn.commit()

        seed_employees(cur)
        conn.commit()

        seed_orders(cur)
        conn.commit()

        seed_order_items(cur)
        conn.commit()

        seed_returns(cur)
        conn.commit()

        seed_shipments(cur)
        conn.commit()

        seed_product_reviews(cur)
        conn.commit()

        seed_loyalty_points(cur)
        conn.commit()

        seed_inventory_snapshots(cur)
        conn.commit()

        print("Done! Seeded ~143K rows across 14 tables")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
