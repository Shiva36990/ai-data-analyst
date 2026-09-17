"""
Generate a realistic e-commerce dataset for the AI Data Analyst project.

This version uses BULK INSERTS instead of inserting one row at a time.

Usage on Windows PowerShell:

$env:SEED_DATABASE_URL="postgresql+psycopg://neondb_owner:YOUR_PASSWORD@YOUR_HOST/neondb?sslmode=require"
python scripts/seed_database.py
"""

import os
import random
from datetime import date, timedelta

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

SEED_DATABASE_URL = (
    os.getenv("SEED_DATABASE_URL")
    or os.getenv("DATABASE_URL")
)

if not SEED_DATABASE_URL:
    raise RuntimeError(
        "Set SEED_DATABASE_URL or DATABASE_URL before running the seeder."
    )


engine = create_engine(
    SEED_DATABASE_URL,
    pool_pre_ping=True,
)

fake = Faker("en_IN")

# Makes generated data reproducible
random.seed(42)
Faker.seed(42)


NUM_CUSTOMERS = 2000
NUM_PRODUCTS = 200
NUM_ORDERS = 15000

BATCH_SIZE = 1000


# ============================================================
# REFERENCE DATA
# ============================================================

CATEGORIES = [
    "Electronics",
    "Furniture",
    "Clothing",
    "Sports",
    "Beauty",
    "Home & Kitchen",
    "Books",
    "Accessories",
]


CATEGORY_PRICE_PROFILE = {
    "Electronics": (1500, 60000, 0.72),
    "Furniture": (2000, 45000, 0.55),
    "Clothing": (400, 4000, 0.45),
    "Sports": (300, 8000, 0.50),
    "Beauty": (150, 3000, 0.40),
    "Home & Kitchen": (300, 10000, 0.50),
    "Books": (150, 1200, 0.60),
    "Accessories": (200, 5000, 0.45),
}


SEGMENTS = [
    "Consumer",
    "Corporate",
    "Small Business",
]


CHANNELS = [
    "Website",
    "Mobile App",
    "Marketplace",
    "Retail Store",
]


PAYMENT_METHODS = [
    "UPI",
    "Credit Card",
    "Debit Card",
    "Net Banking",
    "COD",
]


STATUSES = [
    "Completed",
    "Cancelled",
    "Returned",
    "Pending",
]


STATUS_WEIGHTS = [
    0.82,
    0.06,
    0.05,
    0.07,
]


STATES = [
    "Telangana",
    "Maharashtra",
    "Karnataka",
    "Tamil Nadu",
    "Delhi",
    "West Bengal",
    "Gujarat",
    "Uttar Pradesh",
    "Rajasthan",
    "Kerala",
]


START_DATE = date(2023, 1, 1)
END_DATE = date(2026, 8, 31)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def chunks(data, size):
    """Split a list into smaller batches."""
    for i in range(0, len(data), size):
        yield data[i:i + size]


def random_date(start, end):
    delta_days = (end - start).days
    return start + timedelta(
        days=random.randint(0, delta_days)
    )


def get_order_multiplier(order_date, category, channel):
    """
    Creates intentional business patterns:

    1. December seasonal sales increase
    2. Electronics dip during August 2025
    3. Mobile app growth effect
    """

    multiplier = 1.0

    # December seasonality
    if order_date.month == 12:
        multiplier *= 1.30

    # Intentional Electronics anomaly
    if (
        order_date.year == 2025
        and order_date.month == 8
        and category == "Electronics"
    ):
        multiplier *= 0.45

    # Mobile App performs slightly better
    if channel == "Mobile App":
        multiplier *= 1.10

    return multiplier


def generate_weighted_order_date_and_category():
    """
    Generates dates/categories using probability so the dataset
    contains discoverable patterns.
    """

    while True:

        order_date = random_date(
            START_DATE,
            END_DATE
        )

        category = random.choice(CATEGORIES)

        channel = random.choices(
            CHANNELS,
            weights=[0.35, 0.30, 0.20, 0.15]
        )[0]

        multiplier = get_order_multiplier(
            order_date,
            category,
            channel
        )

        # Normalize probability
        probability = min(multiplier / 1.43, 1.0)

        if random.random() <= probability:
            return order_date, category, channel


# ============================================================
# DATABASE CLEANUP
# ============================================================

def clear_existing_data(conn):

    print("\nClearing old seeded data...")

    conn.execute(
        text(
            """
            TRUNCATE TABLE
                order_items,
                orders,
                products,
                categories,
                customers
            RESTART IDENTITY CASCADE;
            """
        )
    )

    print("Old data cleared.")


# ============================================================
# CREATE CUSTOMERS
# ============================================================

def create_customers(conn):

    print(f"\nGenerating {NUM_CUSTOMERS} customers...")

    customers = []
    customer_segments = {}

    for customer_id in range(1, NUM_CUSTOMERS + 1):

        state = random.choice(STATES)

        segment = random.choices(
            SEGMENTS,
            weights=[0.65, 0.15, 0.20]
        )[0]

        customer_segments[customer_id] = segment

        customers.append(
            {
                "customer_id": customer_id,
                "customer_name": fake.name(),
                "email": f"customer{customer_id}@example.com",
                "city": fake.city(),
                "state": state,
                "country": "India",
                "customer_segment": segment,
                "signup_date": random_date(
                    START_DATE,
                    END_DATE
                ),
            }
        )

    print("Inserting customers in batches...")

    sql = text(
        """
        INSERT INTO customers
        (
            customer_id,
            customer_name,
            email,
            city,
            state,
            country,
            customer_segment,
            signup_date
        )
        VALUES
        (
            :customer_id,
            :customer_name,
            :email,
            :city,
            :state,
            :country,
            :customer_segment,
            :signup_date
        )
        """
    )

    for batch in chunks(customers, BATCH_SIZE):
        conn.execute(sql, batch)

    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('customers', 'customer_id'),
                :value,
                true
            )
            """
        ),
        {"value": NUM_CUSTOMERS},
    )

    print(f"✓ Inserted {NUM_CUSTOMERS} customers")

    return customer_segments


# ============================================================
# CREATE CATEGORIES
# ============================================================

def create_categories(conn):

    print("\nCreating categories...")

    rows = []

    for category_id, category_name in enumerate(
        CATEGORIES,
        start=1
    ):
        rows.append(
            {
                "category_id": category_id,
                "category_name": category_name,
            }
        )

    conn.execute(
        text(
            """
            INSERT INTO categories
            (
                category_id,
                category_name
            )
            VALUES
            (
                :category_id,
                :category_name
            )
            """
        ),
        rows,
    )

    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('categories', 'category_id'),
                :value,
                true
            )
            """
        ),
        {"value": len(CATEGORIES)},
    )

    category_ids = {
        name: index + 1
        for index, name in enumerate(CATEGORIES)
    }

    print(f"✓ Inserted {len(CATEGORIES)} categories")

    return category_ids


# ============================================================
# CREATE PRODUCTS
# ============================================================

def create_products(conn, category_ids):

    print(f"\nGenerating {NUM_PRODUCTS} products...")

    products = []

    products_by_category = {}

    for product_id in range(1, NUM_PRODUCTS + 1):

        category_name = random.choice(CATEGORIES)

        low, high, cost_ratio = (
            CATEGORY_PRICE_PROFILE[category_name]
        )

        unit_price = round(
            random.uniform(low, high),
            2
        )

        cost_price = round(
            unit_price * cost_ratio,
            2
        )

        product = {
            "product_id": product_id,
            "product_name": (
                f"{fake.word().title()} "
                f"{category_name.replace('&', 'and')}"
                f" Product {product_id}"
            ),
            "category_id": category_ids[category_name],
            "unit_price": unit_price,
            "cost_price": cost_price,
            "active": True,
        }

        products.append(product)

        products_by_category.setdefault(
            category_name,
            []
        ).append(product)

    print("Inserting products in batches...")

    sql = text(
        """
        INSERT INTO products
        (
            product_id,
            product_name,
            category_id,
            unit_price,
            cost_price,
            active
        )
        VALUES
        (
            :product_id,
            :product_name,
            :category_id,
            :unit_price,
            :cost_price,
            :active
        )
        """
    )

    for batch in chunks(products, BATCH_SIZE):
        conn.execute(sql, batch)

    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('products', 'product_id'),
                :value,
                true
            )
            """
        ),
        {"value": NUM_PRODUCTS},
    )

    print(f"✓ Inserted {NUM_PRODUCTS} products")

    return products_by_category


# ============================================================
# CREATE ORDERS + ORDER ITEMS
# ============================================================

def create_orders_and_items(
    conn,
    customer_segments,
    products_by_category,
):

    print(
        f"\nGenerating {NUM_ORDERS} orders "
        "and order items..."
    )

    orders = []
    order_items = []

    order_item_id = 1

    for order_id in range(1, NUM_ORDERS + 1):

        order_date, category, channel = (
            generate_weighted_order_date_and_category()
        )

        customer_id = random.randint(
            1,
            NUM_CUSTOMERS
        )

        customer_segment = customer_segments[
            customer_id
        ]

        state = random.choice(STATES)

        status = random.choices(
            STATUSES,
            weights=STATUS_WEIGHTS
        )[0]

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": order_date,
                "status": status,
                "payment_method": random.choice(
                    PAYMENT_METHODS
                ),
                "sales_channel": channel,
                "shipping_city": fake.city(),
                "shipping_state": state,
            }
        )

        available_products = (
            products_by_category.get(category)
            or [
                product
                for products in products_by_category.values()
                for product in products
            ]
        )

        # Corporate customers tend to have higher AOV
        if customer_segment == "Corporate":

            num_items = random.randint(3, 6)

            # Prefer higher-priced products
            available_products = sorted(
                available_products,
                key=lambda x: x["unit_price"],
                reverse=True,
            )

            preferred_products = available_products[
                :max(
                    1,
                    len(available_products) // 2
                )
            ]

        else:

            num_items = random.randint(1, 4)

            preferred_products = available_products

        for _ in range(num_items):

            product = random.choice(
                preferred_products
            )

            quantity = random.randint(1, 4)

            discount = random.choice(
                [0, 0, 0, 5, 10, 15]
            )

            order_items.append(
                {
                    "order_item_id": order_item_id,
                    "order_id": order_id,
                    "product_id": product[
                        "product_id"
                    ],
                    "quantity": quantity,
                    "unit_price": product[
                        "unit_price"
                    ],
                    "discount": discount,
                }
            )

            order_item_id += 1

    print(
        f"Generated {len(orders)} orders"
    )

    print(
        f"Generated {len(order_items)} order items"
    )

    # --------------------------------------------------------
    # INSERT ORDERS IN BATCHES
    # --------------------------------------------------------

    print("\nInserting orders...")

    order_sql = text(
        """
        INSERT INTO orders
        (
            order_id,
            customer_id,
            order_date,
            status,
            payment_method,
            sales_channel,
            shipping_city,
            shipping_state
        )
        VALUES
        (
            :order_id,
            :customer_id,
            :order_date,
            :status,
            :payment_method,
            :sales_channel,
            :shipping_city,
            :shipping_state
        )
        """
    )

    inserted = 0

    for batch in chunks(orders, BATCH_SIZE):

        conn.execute(
            order_sql,
            batch
        )

        inserted += len(batch)

        print(
            f"  ✓ {inserted}/{NUM_ORDERS} orders"
        )

    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('orders', 'order_id'),
                :value,
                true
            )
            """
        ),
        {"value": NUM_ORDERS},
    )

    # --------------------------------------------------------
    # INSERT ORDER ITEMS IN BATCHES
    # --------------------------------------------------------

    print("\nInserting order items...")

    item_sql = text(
        """
        INSERT INTO order_items
        (
            order_item_id,
            order_id,
            product_id,
            quantity,
            unit_price,
            discount
        )
        VALUES
        (
            :order_item_id,
            :order_id,
            :product_id,
            :quantity,
            :unit_price,
            :discount
        )
        """
    )

    inserted = 0

    for batch in chunks(
        order_items,
        BATCH_SIZE
    ):

        conn.execute(
            item_sql,
            batch
        )

        inserted += len(batch)

        print(
            f"  ✓ {inserted}/{len(order_items)} items"
        )

    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence(
                    'order_items',
                    'order_item_id'
                ),
                :value,
                true
            )
            """
        ),
        {
            "value": len(order_items)
        },
    )

    print(
        f"\n✓ Inserted {NUM_ORDERS} orders"
    )

    print(
        f"✓ Inserted {len(order_items)} order items"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("AI DATA ANALYST - DATABASE SEEDER")
    print("=" * 60)

    with engine.begin() as conn:

        clear_existing_data(conn)

        customer_segments = create_customers(
            conn
        )

        category_ids = create_categories(
            conn
        )

        products_by_category = create_products(
            conn,
            category_ids
        )

        create_orders_and_items(
            conn,
            customer_segments,
            products_by_category,
        )

    print("\n" + "=" * 60)
    print("🎉 DATABASE SEEDING COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()