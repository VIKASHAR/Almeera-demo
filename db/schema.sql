-- Schema definition for Grocery Chatbot Demo

DROP TABLE IF EXISTS affinity;
DROP TABLE IF EXISTS purchase_history;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS promotions;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS products;

-- 1. Products Table
CREATE TABLE products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    brand TEXT NOT NULL,
    price REAL NOT NULL,
    attributes_json TEXT NOT NULL, -- e.g., {"fat_content": "low-fat", "organic": true, "gluten_free": false}
    image_url TEXT,
    product_url TEXT
);

-- 2. Inventory Table (channel-aware stock)
CREATE TABLE inventory (
    sku TEXT NOT NULL,
    channel TEXT CHECK(channel IN ('online', 'in_store')) NOT NULL,
    stock_qty INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sku, channel),
    FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
);

-- 3. Promotions Table
CREATE TABLE promotions (
    promo_id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    discount_pct REAL NOT NULL, -- e.g., 0.15 for 15% discount
    description TEXT NOT NULL,
    valid_until TEXT NOT NULL,  -- YYYY-MM-DD
    FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
);

-- 4. Customers Table
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    preferences_json TEXT NOT NULL -- e.g., {"diet": "low-fat", "allergies": ["nuts"], "favorite_categories": ["Dairy"]}
);

-- 5. Purchase History Table (for transaction mining and personalization)
CREATE TABLE purchase_history (
    transaction_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
);

-- 6. Precomputed Affinity Table (Apriori output)
CREATE TABLE affinity (
    sku_a TEXT NOT NULL,
    sku_b TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    PRIMARY KEY (sku_a, sku_b),
    FOREIGN KEY (sku_a) REFERENCES products(sku) ON DELETE CASCADE,
    FOREIGN KEY (sku_b) REFERENCES products(sku) ON DELETE CASCADE
);
