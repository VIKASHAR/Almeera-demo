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
    
    # 2. SKU Barcode Mapping for Test Cases & Backward Compatibility
    MOCK_TO_ORIGINAL = {
        "D1": "3043931692415",  # Regilait Non-Fat Instant Skimmed Milk Powder (Low-Fat Dairy)
        "D2": "5255010204428",  # Al Badia Full Cream Milk Powder (Whole Dairy)
        "D3": "9504000172572",  # Al Maha Plain Yogurt Low Fat (Low-Fat Yogurt)
        "D4": "7622201693831",  # Kraft Philadelphia Cream Cheese With Chives (Cheese)
        "D5": "8006830991763",  # Mantova Basil Olive Oil (Dairy/Milk Alternative fallback for test)
        "D6": "8719200750913",  # Flora Margarine Buttery (Butter)
        "D7": "9504000172572",  # Yoghurt (Sour Cream fallback)
        "D8": "7622201693831",  # Cream Cheese
        "P1": "9911054000000",  # Tomato Turkey
        "P2": "8006830991763",  # Mantova Basil Olive Oil
        "P3": "5032722305922",  # Biona Organic Garden Spinach
        "P4": "9911328000000",  # Banana Ecuador
        "P5": "9910815000000",  # Garlic Small Pack
        "P6": "4002359019906",  # Dolmio Onion & Garlic Bolognese Sauce
        "P7": "9910009000000",  # Avocado Kenya
        "P8": "9910241000000",  # Lemon Egypt
        "P9": "5032722305922",  # Garden Spinach (Mushroom fallback)
        "G1": "5000157026224",  # Heinz Spaghetti
        "G2": "6281011135897",  # Afia Extra Virgin Olive Oil
        "G3": "6281020101111",  # Luna Tomato Sauce
        "G4": "5285432104549",  # Wooden Bakery Tannour Barley Bread
        "G5": "3043931692415",  # coconut/milk alternative fallback
        "G6": "4002359019906",  # curry/spice fallback
        "G7": "5051777001269",  # Love More Shortbread Fingers (Cereal fallback)
        "G8": "8031459114958",  # Ottima Chopped Tomatoes (Beans fallback)
        "G9": "5000157026224",  # Heinz Spaghetti
        "G10": "6281020101111", # Luna Tomato Sauce
        "G11": "5285432104549", # Wooden Bakery Tannour Barley Bread
    }

    products = []

    # Load original products from products.db if it exists
    orig_db_path = "db/products.db"
    if os.path.exists(orig_db_path):
        try:
            orig_conn = sqlite3.connect(orig_db_path)
            orig_cursor = orig_conn.cursor()
            orig_cursor.execute("SELECT id, name, price, image_url, product_url, category FROM products WHERE price IS NOT NULL AND price > 0.0")
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
        
        # Test Case: D1 (Low-Fat Milk, mapped to Regilait Skimmed) is OUT OF STOCK online, but IN STOCK in store!
        if sku == "3043931692415":
            online_qty = 0
            in_store_qty = 5
            
        # Test Case: G10 (Rao's Premium Marinara, mapped to Luna Tomato Sauce) is completely OUT OF STOCK in both channels to trigger alternatives
        if sku == "6281020101111":
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
        ("PROM1", "5000157026224", 0.20, "20% off Heinz Spaghetti!", "2026-12-31"), # G1 mapped
        ("PROM2", "6281020101111", 0.15, "Save 15% on Luna Tomato Sauce", "2026-12-31"), # G3 mapped
        ("PROM3", "9504000172572", 0.10, "10% Off Healthy Plain Yogurt", "2026-12-31"), # D3 mapped
        ("PROM4", "6281020101111", 0.25, "Luna Tomato Sauce 25% Clearance!", "2026-12-31"), # G10 mapped
    ]
    
    # Add random promotions for about 2% of original products
    existing_promo_skus = {p[1] for p in promotions}
    orig_products_list = [p for p in products if p[0] not in existing_promo_skus]
    
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

    # Map the baskets to original barcodes
    mapped_baskets = {}
    for b_name, b_items in baskets.items():
        mapped_baskets[b_name] = [MOCK_TO_ORIGINAL[item] for item in b_items if item in MOCK_TO_ORIGINAL]
    
    # Generate transactions for Alice, Bob, Charlie first (to make sure they have a history)
    real_customers = ["c1", "c2", "c3"]
    all_customers = real_customers + [f"cust_{i}" for i in range(1, 27)]
    
    tx_counter = 1000
    for cust in all_customers:
        # Determine number of transactions for this customer
        num_tx = random.randint(3, 8)
        
        # Customer-specific biases to ensure personalization works
        preferred_baskets = list(mapped_baskets.keys())
        if cust == "c1": # Healthy Dairy preference + Salad
            preferred_baskets = ["breakfast", "snack", "salad"]
        elif cust == "c2": # Vegan Pasta preference + Salad
            preferred_baskets = ["pasta", "curry", "salad"]
            
        for _ in range(num_tx):
            tx_id = f"TX{tx_counter}"
            tx_counter += 1
            
            # Select a primary basket theme
            theme = random.choice(preferred_baskets)
            base_items = mapped_baskets[theme].copy()
            
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
