import sqlite3
import json
import random
import os
import sys

# Add src to python path to import affinity
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.affinity import compute_and_save_affinity

def seed_database(db_path="db/mvp_demo.db", schema_path="db/schema.sql"):
    print(f"Seeding database at {db_path} with schema {schema_path}...")
    
    # Ensure directories exist
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    
    # 1. Reset tables with schema.sql
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    
    cursor.executescript(schema_sql)
    conn.commit()
    print("Schema applied successfully.")
    
    # 2. Seed Products
    demo_products = [
        # DAIRY
        ("D1", "Organic Low-Fat Milk", "Dairy", "Milk", "Lactaid", 3.49, {"fat_content": "low-fat", "organic": True, "dairy_free": False, "gluten_free": True}),
        ("D2", "Organic Whole Milk", "Dairy", "Milk", "Horizon", 3.99, {"fat_content": "whole", "organic": True, "dairy_free": False, "gluten_free": True}),
        ("D3", "Greek Yogurt Strawberry", "Dairy", "Yogurt", "Chobani", 1.29, {"fat_content": "low-fat", "organic": False, "dairy_free": False, "gluten_free": True}),
        ("D4", "Cheddar Cheese Block", "Dairy", "Cheese", "Tillamook", 4.99, {"fat_content": "regular", "organic": False, "dairy_free": False, "gluten_free": True}),
        ("D5", "Almond Milk Unsweetened", "Dairy", "Milk", "Silk", 3.29, {"fat_content": "low-fat", "organic": False, "dairy_free": True, "gluten_free": True}),
        ("D6", "Salted Butter Block", "Dairy", "Butter", "Kerrygold", 4.49, {"fat_content": "regular", "organic": False, "dairy_free": False, "gluten_free": True}),
        ("D7", "Sour Cream Tub", "Dairy", "Sour Cream", "Daisy", 2.19, {"fat_content": "regular", "organic": False, "dairy_free": False, "gluten_free": True}),
        ("D8", "Cream Cheese Spread", "Dairy", "Cream Cheese", "Philadelphia", 2.99, {"fat_content": "regular", "organic": False, "dairy_free": False, "gluten_free": True}),
        
        # PRODUCE
        ("P1", "Roma Tomatoes", "Produce", "Tomatoes", "Dole", 2.49, {"organic": False, "vegan": True, "gluten_free": True}),
        ("P2", "Fresh Basil Bunch", "Produce", "Herbs", "Organic Girl", 1.99, {"organic": True, "vegan": True, "gluten_free": True}),
        ("P3", "Organic Spinach", "Produce", "Leafy Greens", "Earthbound Farm", 3.49, {"organic": True, "vegan": True, "gluten_free": True}),
        ("P4", "Bananas Bunch", "Produce", "Fruit", "Chiquita", 1.89, {"organic": False, "vegan": True, "gluten_free": True}),
        ("P5", "Fresh Garlic Bulb", "Produce", "Alliums", "Dole", 0.99, {"organic": False, "vegan": True, "gluten_free": True}),
        ("P6", "Yellow Onions Bag", "Produce", "Alliums", "Dole", 2.29, {"organic": False, "vegan": True, "gluten_free": True}),
        ("P7", "Avocados Bag", "Produce", "Fruit", "Hass", 4.99, {"organic": False, "vegan": True, "gluten_free": True}),
        ("P8", "Lemons Bag", "Produce", "Fruit", "Sunkist", 2.99, {"organic": False, "vegan": True, "gluten_free": True}),
        ("P9", "Portobello Mushrooms", "Produce", "Mushrooms", "Dole", 3.49, {"organic": False, "vegan": True, "gluten_free": True}),
        
        # PANTRY / GRAINS
        ("G1", "Spaghetti Pasta", "Pantry/Grains", "Pasta", "Barilla", 1.49, {"organic": False, "vegan": True, "gluten_free": False}),
        ("G2", "Extra Virgin Olive Oil", "Pantry/Grains", "Oil", "Bertolli", 8.99, {"organic": False, "vegan": True, "gluten_free": True}),
        ("G3", "Classic Tomato Sauce", "Pantry/Grains", "Sauce", "Prego", 2.19, {"organic": False, "vegan": True, "gluten_free": True}),
        ("G4", "Jasmine Rice 5lb", "Pantry/Grains", "Rice", "Mahatma", 5.49, {"organic": False, "vegan": True, "gluten_free": True}),
        ("G5", "Organic Coconut Milk", "Pantry/Grains", "Milk Alternative", "Thai Kitchen", 2.79, {"organic": True, "vegan": True, "dairy_free": True, "gluten_free": True}),
        ("G6", "Madras Curry Powder", "Pantry/Grains", "Spices", "McCormick", 3.99, {"organic": False, "vegan": True, "gluten_free": True}),
        ("G7", "Crunchy Honey Oats Cereal", "Pantry/Grains", "Cereal", "Post", 4.29, {"organic": False, "vegan": False, "gluten_free": False}),
        ("G8", "Canned Chickpeas", "Pantry/Grains", "Canned Beans", "Goya", 1.19, {"organic": False, "vegan": True, "gluten_free": True}),
        ("G9", "Penne Pasta", "Pantry/Grains", "Pasta", "Barilla", 1.49, {"organic": False, "vegan": True, "gluten_free": False}),
        ("G10", "Premium Marinara Sauce", "Pantry/Grains", "Sauce", "Rao's", 6.99, {"organic": True, "vegan": True, "gluten_free": True}),
        ("G11", "White Sliced Bread", "Pantry/Grains", "Bakery", "Wonder", 2.49, {"organic": False, "vegan": True, "gluten_free": False}),
    ]

    products = [(sku, name, cat, subcat, brand, price, attr, None, None)
                for sku, name, cat, subcat, brand, price, attr in demo_products]

    # Load original products from products.db if it exists
    orig_db_path = "db/products.db"
    if os.path.exists(orig_db_path):
        try:
            orig_conn = sqlite3.connect(orig_db_path)
            orig_cursor = orig_conn.cursor()
            orig_cursor.execute("SELECT id, name, price, image_url, product_url, category FROM products")
            rows = orig_cursor.fetchall()
            
            orig_count = 0
            for row in rows:
                id_val, name, price, image_url, product_url, category_str = row
                
                # Parse SKU
                sku = product_url.split('/')[-1] if product_url else f"OP-{id_val}"
                if not sku:
                    sku = f"OP-{id_val}"
                    
                # Map Category & Subcategory
                c = category_str.lower() if category_str else ""
                cat = "Pantry/Grains"
                subcat = "General"
                
                if any(k in c for k in ["fruit", "vegetable", "produce", "salad"]):
                    cat = "Produce"
                elif any(k in c for k in ["dairy", "milk", "cheese", "yogurt", "butter", "laban", "cream", "ghee"]):
                    cat = "Dairy"
                elif any(k in c for k in ["bakery", "bread", "pastry", "cake", "donut", "croissant", "buns"]):
                    cat = "Bakery"
                elif any(k in c for k in ["beverage", "juice", "water", "soda", "tea", "coffee", "drink"]):
                    cat = "Beverages"
                elif any(k in c for k in ["snack", "chocolate", "sweet", "chips", "nuts", "biscuit", "candy", "gum", "cracker"]):
                    cat = "Snacks"
                elif any(k in c for k in ["baby", "wipes", "diaper"]):
                    cat = "Baby"
                elif any(k in c for k in ["pet", "dog", "cat"]):
                    cat = "Pet"
                elif any(k in c for k in ["cleaning", "laundry", "household", "cleaner", "tissue", "detergent", "wash", "soap", "dishwash"]):
                    cat = "Household"
                elif any(k in c for k in ["pantry", "grain", "rice", "pasta", "noodle", "sauce", "oil", "spice", "seasoning", "flour", "canned", "jarred", "condiment"]):
                    cat = "Pantry/Grains"
                else:
                    # Fallback based on top level category segment
                    parts = category_str.split(" > ") if category_str else []
                    if parts:
                        top = parts[0].lower()
                        if any(k in top for k in ["food", "grocery", "fresh", "ready to eat"]):
                            cat = "Pantry/Grains"
                        elif any(k in top for k in ["home", "living", "cleaning", "laundry", "electronics", "hardware", "tools", "sports", "health", "fitness", "personal care"]):
                            cat = "Household"
                
                parts = category_str.split(" > ") if category_str else []
                if len(parts) >= 2:
                    subcat = parts[1]
                elif parts:
                    subcat = parts[0]
                    
                # Determine Brand
                name_parts = name.strip().split() if name else []
                brand = name_parts[0] if name_parts else "Generic"
                
                # Map Price (convert QAR to USD equivalent)
                usd_price = round(price / 3.64, 2) if price is not None else 0.0
                
                # Tag Attributes
                name_lower = name.lower() if name else ""
                organic = "organic" in name_lower or "organic" in c
                vegan = "vegan" in name_lower or "vegan" in c or cat == "Produce"
                gluten_free = "gluten free" in name_lower or "gluten-free" in name_lower or "gluten-free" in c
                
                fat_content = "regular"
                if any(k in name_lower for k in ["low fat", "low-fat", "non fat", "non-fat", "skimmed"]):
                    fat_content = "low-fat"
                elif any(k in name_lower for k in ["whole milk", "full cream", "full-cream"]):
                    fat_content = "whole"
                    
                dairy_free = True
                if cat == "Dairy" or any(k in name_lower for k in ["milk", "cheese", "yogurt", "butter", "cream"]):
                    dairy_free = False
                if "dairy free" in name_lower or "dairy-free" in name_lower:
                    dairy_free = True
                    
                attr = {
                    "organic": organic,
                    "vegan": vegan,
                    "gluten_free": gluten_free,
                    "fat_content": fat_content,
                    "dairy_free": dairy_free
                }
                
                products.append((sku, name, cat, subcat, brand, usd_price, attr, image_url, product_url))
                orig_count += 1
            orig_conn.close()
            print(f"Loaded {orig_count} original products from {orig_db_path}.")
        except Exception as e:
            print(f"Error loading original products: {e}")

    cursor.executemany(
        "INSERT INTO products (sku, name, category, subcategory, brand, price, attributes_json, image_url, product_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(sku, name, cat, subcat, brand, price, json.dumps(attr), img, url) for sku, name, cat, subcat, brand, price, attr, img, url in products]
    )
    conn.commit()
    print(f"Seeded {len(products)} products total.")
    
    # 3. Seed Inventory
    # We populate both 'online' and 'in_store' channels
    inventory_records = []
    for sku, name, cat, subcat, brand, price, attr, img, url in products:
        # Default quantities
        online_qty = random.randint(10, 50)
        in_store_qty = random.randint(10, 50)
        
        # Test Case: D1 (Low-Fat Milk) is OUT OF STOCK online, but IN STOCK in store!
        if sku == "D1":
            online_qty = 0
            in_store_qty = 5
            
        # Test Case: G10 (Rao's Premium Marinara) is completely OUT OF STOCK in both channels to trigger alternatives
        if sku == "G10":
            online_qty = 0
            in_store_qty = 0
            
        inventory_records.append((sku, 'online', online_qty))
        inventory_records.append((sku, 'in_store', in_store_qty))
        
    cursor.executemany(
        "INSERT INTO inventory (sku, channel, stock_qty) VALUES (?, ?, ?)",
        inventory_records
    )
    conn.commit()
    print("Seeded inventory stock levels (with custom out-of-stock scenarios).")
    
    # 4. Seed Promotions
    promotions = [
        ("PROM1", "G1", 0.20, "20% off Spaghetti Pasta!", "2026-12-31"),
        ("PROM2", "G3", 0.15, "Save 15% on Prego Tomato Sauce", "2026-12-31"),
        ("PROM3", "D3", 0.10, "10% Off Healthy Greek Yogurt", "2026-12-31"),
        ("PROM4", "G10", 0.25, "Rao's Marinara 25% Clearance!", "2026-12-31"),
    ]
    
    # Add random promotions for about 2% of original products
    existing_promo_skus = {p[1] for p in promotions}
    orig_products_list = [p for p in products if p[0] not in existing_promo_skus and (p[0].startswith("6") or p[0].startswith("8") or p[0].startswith("5"))]
    
    random.seed(42)
    promoted_sample = random.sample(orig_products_list, min(len(orig_products_list), int(0.02 * len(orig_products_list))))
    for i, p in enumerate(promoted_sample):
        sku = p[0]
        discount = random.choice([0.10, 0.15, 0.20, 0.25])
        pct_str = f"{int(discount * 100)}%"
        desc = f"Special Deal: {pct_str} off {p[1]}!"
        promo_id = f"OPROM_{i}"
        promotions.append((promo_id, sku, discount, desc, "2026-12-31"))

    cursor.executemany(
        "INSERT INTO promotions (promo_id, sku, discount_pct, description, valid_until) VALUES (?, ?, ?, ?, ?)",
        promotions
    )
    conn.commit()
    print(f"Seeded {len(promotions)} active promotions.")
    
    # 5. Seed Customers
    customers = [
        ("c1", "Alice (Healthy & Low-Fat)", {"diet": "low-fat", "allergies": ["nuts"], "favorite_categories": ["Dairy"]}),
        ("c2", "Bob (Vegan Pasta Lover)", {"diet": "vegan", "allergies": [], "favorite_categories": ["Produce", "Pantry/Grains"]}),
        ("c3", "Charlie (Budget Grains)", {"diet": "none", "allergies": [], "favorite_categories": ["Dairy", "Pantry/Grains"]}),
    ]
    cursor.executemany(
        "INSERT INTO customers (customer_id, name, preferences_json) VALUES (?, ?, ?)",
        [(cid, name, json.dumps(prefs)) for cid, name, prefs in customers]
    )
    conn.commit()
    print("Seeded 3 demo customer profiles.")
    
    # 6. Seed Purchase History (Coherent transaction baskets for Apriori)
    # We will generate about 150 transactions for 30 synthetic customers to build solid association rules
    transaction_records = []
    
    # Basket templates
    baskets = {
        "pasta": ["G1", "G3", "P1", "P2", "P5", "G2"], # Spaghetti + Tomato Sauce + Roma Tomatoes + Basil + Garlic + Olive Oil
        "breakfast": ["G7", "D2", "P4"],               # Honey Oats Cereal + Whole Milk + Bananas
        "curry": ["G4", "G5", "G6", "P6"],              # Jasmine Rice + Coconut Milk + Curry Powder + Onions
        "snack": ["D3", "P4", "D5"],                   # Greek Yogurt + Bananas + Almond Milk
        "baking": ["D6", "D8", "G11"],                 # Butter + Cream Cheese + White Bread (Toast)
        "salad": ["P3", "P1", "P7", "G2", "P8"],       # Spinach + Tomatoes + Avocado + Olive Oil + Lemon
    }
    
    # Generate transactions for Alice, Bob, Charlie first (to make sure they have a history)
    real_customers = ["c1", "c2", "c3"]
    all_customers = real_customers + [f"cust_{i}" for i in range(1, 25)]
    
    tx_counter = 1000
    for cust in all_customers:
        # Determine number of transactions for this customer
        num_tx = random.randint(3, 8)
        
        # Customer-specific biases to ensure personalization works
        preferred_baskets = list(baskets.keys())
        if cust == "c1": # Healthy Dairy preference + Salad
            preferred_baskets = ["breakfast", "snack", "salad"]
        elif cust == "c2": # Vegan Pasta preference + Salad
            preferred_baskets = ["pasta", "curry", "salad"]
            
        for _ in range(num_tx):
            tx_id = f"TX{tx_counter}"
            tx_counter += 1
            
            # Select a primary basket theme
            theme = random.choice(preferred_baskets)
            base_items = baskets[theme].copy()
            
            # Decide transaction items (at least some items from the theme)
            items_bought = []
            for item in base_items:
                if random.random() < 0.85: # 85% chance to buy items in the theme basket
                    items_bought.append(item)
                    
            # 15% chance to add 1-2 random products from another category
            if random.random() < 0.3:
                random_item = random.choice(products)[0]
                if random_item not in items_bought:
                    items_bought.append(random_item)
                    
            # Insert items bought in this transaction
            for sku in items_bought:
                qty = random.randint(1, 3)
                transaction_records.append((tx_id, cust, sku, qty))
                
    cursor.executemany(
        "INSERT INTO purchase_history (transaction_id, customer_id, sku, qty) VALUES (?, ?, ?, ?)",
        transaction_records
    )
    conn.commit()
    print(f"Generated {tx_counter - 1000} synthetic transactions across {len(all_customers)} customers.")
    
    conn.close()
    
    # 7. Precompute Affinity using Apriori/association rules
    print("Running affinity generation job...")
    compute_and_save_affinity(db_path)
    
if __name__ == "__main__":
    db = "db/mvp_demo.db"
    schema = "db/schema.sql"
    if len(sys.argv) > 1:
        db = sys.argv[1]
    if len(sys.argv) > 2:
        schema = sys.argv[2]
        
    seed_database(db, schema)
