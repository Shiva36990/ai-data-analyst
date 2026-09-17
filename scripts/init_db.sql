-- AI Data Analyst -- schema + indexes + read-only application role.
-- Runs automatically via docker-compose (mounted into
-- /docker-entrypoint-initdb.d/). For a manually-managed Postgres
-- instance, run this once with: psql -f scripts/init_db.sql

CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(150) NOT NULL,
    email VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100) DEFAULT 'India',
    customer_segment VARCHAR(50),
    signup_date DATE
);

CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    category_id INTEGER REFERENCES categories(category_id),
    unit_price NUMERIC(12, 2) NOT NULL,
    cost_price NUMERIC(12, 2),
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status VARCHAR(50),
    payment_method VARCHAR(50),
    sales_channel VARCHAR(50),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(order_id),
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    discount NUMERIC(5, 2) DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);

-- Optional: query audit log. The application connection (below) is
-- NOT granted write access to this table -- log writes should go
-- through a separate, non-agent service connection if you add them.
CREATE TABLE IF NOT EXISTS agent_query_logs (
    log_id BIGSERIAL PRIMARY KEY,
    thread_id VARCHAR(100),
    question TEXT,
    generated_sql TEXT,
    success BOOLEAN,
    execution_ms INTEGER,
    row_count INTEGER,
    retry_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- Read-only role for the AI agent's DATABASE_URL.
-- Change the password before using this anywhere but local dev.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_readonly') THEN
        CREATE USER ai_readonly WITH PASSWORD 'ShivaPass123';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE neondb TO ai_readonly;
GRANT USAGE ON SCHEMA public TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ai_readonly;

-- Explicitly revoke access to the audit log table from the read-only
-- role in case a future migration grants schema-wide SELECT again.
REVOKE ALL ON agent_query_logs FROM ai_readonly;
