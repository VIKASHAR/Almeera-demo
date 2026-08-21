import sqlite3
import json
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db", "mvp_demo.db"))

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Enable WAL mode for better concurrent read/write performance
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    # Parse attributes_json if it exists
    if 'attributes_json' in d:
        try:
            d['attributes_json'] = json.loads(d['attributes_json'])
        except Exception:
            pass
    return d

def search_products(category=None, query_str=None, attributes=None, price_max=None, channel='online', raw_query=None, limit=None, exclude_categories=None, exclude_subcategories=None):
    """
    Search products based on category, query text, attributes, and max price.
    Also returns stock info for the specified channel. Supports tokenized matching, attribute normalization, and pure budget queries.
    """
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    query = """
        SELECT p.*, i.stock_qty, i.channel 
        FROM products p
        LEFT JOIN inventory i ON p.sku = i.sku AND i.channel = ?
        WHERE p.price > 0.0
    """
    params = [channel]
    
    norm_query_str = None
    norm_raw_query = None

    if category:
        query += " AND p.category = ?"
        params.append(category)
        
    if query_str or raw_query:
        # Use the module-level normalize_term for consistent normalization (includes brand names)
        norm_query_str = normalize_term(query_str) if query_str else None
        norm_raw_query = normalize_term(raw_query) if raw_query else None
        
        # Build multi-term matching (exact phrase OR individual token matches)
        term_filters = []
        
        target_texts = [t for t in [norm_query_str, norm_raw_query] if t]
        for txt in target_texts:
            # 1. Full phrase match
            term_filters.append("(p.name LIKE ? OR p.subcategory LIKE ? OR p.brand LIKE ? OR p.category LIKE ?)")
            term = f"%{txt}%"
            params.extend([term, term, term, term])
            
            # 2. Tokenized word match for multi-word queries (e.g., 'pet food', 'cat food')
            search_stop_words = {
                'food', 'item', 'items', 'buy', 'find', 'show', 'need',
                'fresh', 'whole', 'natural', 'raw', 'organic', 'pure',
                'premium', 'best', 'quality', 'good', 'great', 'nice',
                'some', 'the', 'any', 'all', 'our', 'your'
            }
            words = [w.strip() for w in txt.split() if len(w.strip()) > 2 and w.strip() not in search_stop_words]
            for w in words:
                term_filters.append("(p.name LIKE ? OR p.subcategory LIKE ? OR p.brand LIKE ? OR p.category LIKE ?)")
                w_term = f"%{w}%"
                params.extend([w_term, w_term, w_term, w_term])
                
        if term_filters:
            query += " AND (" + " OR ".join(term_filters) + ")"
    elif price_max is not None:
        # Pure budget query without keyword (e.g. "show me items under 2 QAR")
        query += " AND i.stock_qty > 0"
        
    if price_max:
        query += " AND p.price <= ?"
        params.append(price_max)

    # Exclude specified categories (e.g. exclude Meat & Seafood when user asks for Produce/fruits)
    if exclude_categories:
        for exc_cat in exclude_categories:
            query += " AND p.category != ?"
            params.append(exc_cat)

    # Exclude specific subcategories (e.g. "Nuts, Dates & Dried Food" when user asks for fruit)
    if exclude_subcategories:
        for exc_sub in exclude_subcategories:
            query += " AND p.subcategory != ?"
            params.append(exc_sub)
        
    raw_or_query_lower = (raw_query or query_str or '').lower()
    is_veg_query = 1 if any(k in raw_or_query_lower for k in ['vegetable', 'vegetables', 'veggie', 'veggies', 'onion', 'tomato', 'potato', 'spinach', 'cucumber', 'carrot', 'lettuce', 'garlic', 'mushroom', 'broccoli', 'zucchini', 'pepper', 'cabbage', 'eggplant']) else 0
    is_fruit_query = 1 if any(k in raw_or_query_lower for k in ['fruit', 'fruits', 'frutis', 'apple', 'banana', 'orange', 'mango', 'grape', 'lemon', 'lime', 'watermelon', 'peach', 'pear', 'kiwi', 'strawberry', 'melon', 'nectarine']) else 0
    user_wants_processed = any(w in raw_or_query_lower for w in ['bean', 'beans', 'sauce', 'paste', 'canned', 'jam', 'jelly', 'syrup', 'preserve', 'chips'])
    
    query += """
        ORDER BY 
            CASE 
                -- 0. Non-food / processed penalty when searching for fresh produce
                WHEN (p.category = 'Produce' OR ? = 1 OR ? = 1) AND ? = 0 AND (
                    LOWER(p.name) LIKE '%beans in%' OR LOWER(p.name) LIKE '%baked beans%' OR 
                    LOWER(p.name) LIKE '%jam%' OR LOWER(p.name) LIKE '%jelly%' OR LOWER(p.name) LIKE '%syrup%' OR
                    p.subcategory IN ('Honey & Jams', 'Canned Vegetables', 'Canned & Jarred', 'Special Diet')
                ) THEN 8
                -- 1. Direct fresh produce product name match boost
                WHEN p.category = 'Produce' AND (p.subcategory IN ('Fresh Vegetables', 'Fresh Fruit', 'Fruit & Vegetables', 'Fresh Produce', 'Fruit Cuts') OR p.subcategory = 'Uncategorized') AND LOWER(p.name) LIKE ? THEN 0
                -- 2. Direct product name match boost
                WHEN LOWER(p.name) LIKE ? THEN 1
                -- 3. Vegetable-specific boost
                WHEN ? = 1 AND p.category = 'Produce' AND (
                    p.subcategory = 'Fresh Vegetables' OR
                    LOWER(p.name) LIKE '%onion%' OR LOWER(p.name) LIKE '%tomato%' OR
                    LOWER(p.name) LIKE '%spinach%' OR LOWER(p.name) LIKE '%cucumber%' OR
                    LOWER(p.name) LIKE '%lettuce%' OR LOWER(p.name) LIKE '%potato%' OR
                    LOWER(p.name) LIKE '%carrot%' OR LOWER(p.name) LIKE '%garlic%' OR
                    LOWER(p.name) LIKE '%mushroom%' OR LOWER(p.name) LIKE '%broccoli%' OR
                    LOWER(p.name) LIKE '%zucchini%' OR LOWER(p.name) LIKE '%pepper%' OR
                    LOWER(p.name) LIKE '%cabbage%' OR LOWER(p.name) LIKE '%eggplant%'
                ) THEN 2
                -- 4. Fruit-specific boost
                WHEN ? = 1 AND p.category = 'Produce' AND (
                    p.subcategory IN ('Fresh Fruit', 'Fruit Cuts') OR
                    LOWER(p.name) LIKE '%banana%' OR LOWER(p.name) LIKE '%apple%' OR
                    LOWER(p.name) LIKE '%mango%' OR LOWER(p.name) LIKE '%avocado%' OR
                    LOWER(p.name) LIKE '%lemon%' OR LOWER(p.name) LIKE '%orange%' OR
                    LOWER(p.name) LIKE '%grape%' OR LOWER(p.name) LIKE '%strawberr%' OR
                    LOWER(p.name) LIKE '%watermelon%' OR LOWER(p.name) LIKE '%pineapple%' OR
                    LOWER(p.name) LIKE '%kiwi%' OR LOWER(p.name) LIKE '%peach%' OR
                    LOWER(p.name) LIKE '%pear%' OR LOWER(p.name) LIKE '%melon%' OR
                    LOWER(p.name) LIKE '%nectarine%'
                ) THEN 2
                -- 5. General fresh produce
                WHEN p.category = 'Produce' AND p.subcategory IN ('Fresh Vegetables', 'Fresh Fruit', 'Fruit & Vegetables', 'Fresh Produce', 'Fruit Cuts') THEN 3
                -- Bread boosts
                WHEN LOWER(p.name) LIKE '%sliced bread%' OR LOWER(p.name) LIKE '%white bread%' OR LOWER(p.name) LIKE '%brown bread%' OR LOWER(p.name) LIKE '%tannour%bread%' THEN 4
                WHEN LOWER(p.name) LIKE '%bread%' AND LOWER(p.name) NOT LIKE '%breadstick%' AND LOWER(p.name) NOT LIKE '%breaded%' AND LOWER(p.name) NOT LIKE '%bread bin%' AND LOWER(p.name) NOT LIKE '%breading%' AND LOWER(p.name) NOT LIKE '%crumbs%' THEN 5
                -- Pet food boosts
                WHEN LOWER(p.name) LIKE '%cat food%' OR LOWER(p.name) LIKE '%dog food%' OR LOWER(p.name) LIKE '%pet food%' OR LOWER(p.subcategory) LIKE '%food%' THEN 6
                WHEN LOWER(p.brand) IN ('purina', 'whiskas', 'friskies', 'pedigree', 'plaisir', 'dreamies', 'felix') OR LOWER(p.name) LIKE '%whiskas%' OR LOWER(p.name) LIKE '%friskies%' OR LOWER(p.name) LIKE '%pedigree%' THEN 7
                WHEN LOWER(p.name) LIKE '%breadstick%' THEN 8
                WHEN p.subcategory != 'Uncategorized' THEN 9
                ELSE 10
            END,
            i.stock_qty DESC
    """
        
    boost_param = f"%{norm_query_str}%" if norm_query_str else "%nonexistent_match%"
    params.extend([is_veg_query, is_fruit_query, 1 if user_wants_processed else 0, boost_param, boost_param, is_veg_query, is_fruit_query])
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        
    cursor.execute(query, params)
    products = cursor.fetchall()
    
    # Category Fallback: If text search yielded 0 items under a specific category, fetch all in-stock items in that category
    if not products and category:
        fallback_query = """
            SELECT p.*, i.stock_qty, i.channel 
            FROM products p
            LEFT JOIN inventory i ON p.sku = i.sku AND i.channel = ?
            WHERE p.price > 0.0 AND p.category = ?
        """
        fb_params = [channel, category]
        if price_max:
            fallback_query += " AND p.price <= ?"
            fb_params.append(price_max)
        if exclude_categories:
            for exc_cat in exclude_categories:
                fallback_query += " AND p.category != ?"
                fb_params.append(exc_cat)
        if exclude_subcategories:
            for exc_sub in exclude_subcategories:
                fallback_query += " AND p.subcategory != ?"
                fb_params.append(exc_sub)
        is_veg_query = any(k in (raw_query or query_str or '').lower() for k in ['vegetable', 'vegetables', 'veggie', 'veggies', 'onion', 'tomato', 'potato', 'spinach', 'cucumber', 'carrot', 'lettuce', 'garlic', 'mushroom'])
        if is_veg_query:
            fallback_query += """
                ORDER BY 
                    CASE 
                        WHEN p.category = 'Produce' AND (LOWER(p.subcategory) LIKE '%vegetable%' OR LOWER(p.name) LIKE '%onion%' OR LOWER(p.name) LIKE '%tomato%' OR LOWER(p.name) LIKE '%spinach%' OR LOWER(p.name) LIKE '%cucumber%' OR LOWER(p.name) LIKE '%lettuce%' OR LOWER(p.name) LIKE '%potato%' OR LOWER(p.name) LIKE '%carrot%' OR LOWER(p.name) LIKE '%garlic%' OR LOWER(p.name) LIKE '%mushroom%') THEN 1
                        WHEN p.category = 'Produce' AND LOWER(p.subcategory) LIKE '%vegetable%' THEN 2
                        WHEN p.category = 'Produce' AND LOWER(p.subcategory) LIKE '%fruit%' THEN 3
                        ELSE 4
                    END,
                    i.stock_qty DESC
            """
        else:
            fallback_query += """
                ORDER BY 
                    CASE 
                        WHEN p.category = 'Produce' AND LOWER(p.subcategory) LIKE '%fruit%' THEN 1
                        WHEN p.category = 'Produce' AND LOWER(p.subcategory) LIKE '%vegetable%' THEN 2
                        WHEN LOWER(p.name) LIKE '%sliced bread%' OR LOWER(p.name) LIKE '%white bread%' OR LOWER(p.name) LIKE '%brown bread%' THEN 3
                        WHEN LOWER(p.name) LIKE '%bread%' AND LOWER(p.name) NOT LIKE '%breadstick%' AND LOWER(p.name) NOT LIKE '%breaded%' AND LOWER(p.name) NOT LIKE '%crumbs%' THEN 4
                        WHEN p.subcategory != 'Uncategorized' AND (p.name LIKE '%Food%' OR p.subcategory LIKE '%Food%' OR p.name LIKE '%Cat%' OR p.name LIKE '%Dog%') THEN 5
                        ELSE 6
                    END,
                    i.stock_qty DESC
            """
        if limit is not None:
            fallback_query += " LIMIT ?"
            fb_params.append(limit)
            
        cursor.execute(fallback_query, fb_params)
        products = cursor.fetchall()

    conn.close()
    
    # Filter by attributes_json in python with attribute normalization
    if attributes:
        filtered = []
        for p in products:
            match = True
            p_attr = p.get('attributes_json', {})
            for k, v in attributes.items():
                if k == 'fat_content':
                    target_fat = str(v).lower()
                    actual_fat = str(p_attr.get('fat_content', '')).lower()
                    if target_fat in ('low-fat', 'non-fat', 'skimmed', '0%', '0% fat', 'fat-free', 'skim'):
                        if actual_fat not in ('low-fat', 'non-fat', 'skimmed', '0%', '0% fat', 'fat-free', 'skim'):
                            match = False
                            break
                    elif target_fat in ('full-fat', 'whole', 'regular'):
                        if actual_fat not in ('full-fat', 'whole', 'regular'):
                            match = False
                            break
                elif k == 'vegan':
                    if v is True:
                        if p.get('category') in ('Dairy', 'Meat & Seafood') and not (p_attr.get('dairy_free') is True or p_attr.get('plant_based') is True):
                            match = False
                            break
                        if p_attr.get('vegan') is False:
                            match = False
                            break
                elif k == 'gluten_free':
                    if p_attr.get('gluten_free') != v:
                        match = False
                        break
                elif k == 'organic':
                    if p_attr.get('organic') != v:
                        match = False
                        break
                else:
                    if p_attr.get(k) != v:
                        match = False
                        break
            if match:
                filtered.append(p)
        return filtered
        
    return products

def get_products_by_skus(sku_list):
    """
    Fetches full product records directly for a list of SKUs.
    """
    if not sku_list:
        return []
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in sku_list)
    query = f"SELECT * FROM products WHERE sku IN ({placeholders}) AND price > 0.0"
    cursor.execute(query, list(sku_list))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_alternatives(sku, in_stock_only=True, channel='online'):
    """
    Finds alternative products in the same category/subcategory when a product is out of stock.
    """
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # Get the details of the requested sku first
    cursor.execute("SELECT category, subcategory FROM products WHERE sku = ?", (sku,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        return []
        
    # Query other products in same subcategory
    query = """
        SELECT p.*, i.stock_qty, i.channel 
        FROM products p
        JOIN inventory i ON p.sku = i.sku AND i.channel = ?
        WHERE p.subcategory = ? AND p.sku != ? AND p.price > 0.0
    """
    params = [channel, target['subcategory'], sku]
    
    if in_stock_only:
        query += " AND i.stock_qty > 0"
        
    query += " ORDER BY i.stock_qty DESC, p.price ASC LIMIT 10"
    
    cursor.execute(query, params)
    alternatives = cursor.fetchall()
    
    # If no alternatives in subcategory, broaden to same category
    if not alternatives:
        query = """
            SELECT p.*, i.stock_qty, i.channel 
            FROM products p
            JOIN inventory i ON p.sku = i.sku AND i.channel = ?
            WHERE p.category = ? AND p.sku != ? AND p.price > 0.0
        """
        params = [channel, target['category'], sku]
        if in_stock_only:
            query += " AND i.stock_qty > 0"
        query += " ORDER BY i.stock_qty DESC, p.price ASC LIMIT 10"
        cursor.execute(query, params)
        alternatives = cursor.fetchall()
        
    conn.close()
    return alternatives

def check_inventory(sku_list, channel='online'):
    """
    Checks stock levels for a list of SKUs in a channel.
    """
    if not sku_list:
        return {}
        
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    placeholders = ",".join("?" for _ in sku_list)
    query = f"""
        SELECT sku, stock_qty 
        FROM inventory 
        WHERE channel = ? AND sku IN ({placeholders})
    """
    cursor.execute(query, [channel] + list(sku_list))
    rows = cursor.fetchall()
    conn.close()
    
    return {row['sku']: row['stock_qty'] for row in rows}

def get_active_offers(sku_list):
    """
    Fetches active promotions for a list of SKUs.
    """
    if not sku_list:
        return []
        
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    placeholders = ",".join("?" for _ in sku_list)
    query = f"""
        SELECT promo_id, sku, discount_pct, description, valid_until 
        FROM promotions 
        WHERE sku IN ({placeholders})
          AND valid_until >= date('now')
    """
    cursor.execute(query, list(sku_list))
    offers = cursor.fetchall()
    conn.close()
    return offers

def normalize_term(txt):
    if not txt:
        return ""
    txt = txt.lower().strip()
    # Normalize common brand/ingredient spelling variations
    replacements = {
        "maggei": "maggi",
        "maggie": "maggi",
        "magge": "maggi",
        "meggi": "maggi",
        "briyani": "biryani",
        "biriyani": "biryani",
        "spageti": "spaghetti",
        "spagetti": "spaghetti",
        "chiken": "chicken",
        "tomatox": "tomato",
        "tomatos": "tomato",
        "tomatoes": "tomato",
        "tomatoe": "tomato"
    }
    for k, v in replacements.items():
        txt = txt.replace(k, v)
        
    # Plural normalization
    if txt in ("tomatos", "tomatoes", "tomatoe"):
        txt = "tomato"
    elif txt in ("fruits", "fruit"):
        txt = "fruit"
    elif txt in ("vegetables", "veggies", "veggie"):
        txt = "vegetable"
    elif txt in ("breads", "bread"):
        txt = "bread"
    elif txt in ("pastas", "pasta"):
        txt = "pasta"
    elif txt in ("cheeses", "cheese"):
        txt = "cheese"
    elif txt in ("milks", "milk"):
        txt = "milk"
    return txt

FOOD_NOUNS_LIST = [
    'chicken', 'beef', 'lamb', 'meat', 'mutton', 'turkey', 'fish', 'salmon', 'tuna', 'seafood', 'shrimp', 'prawn',
    'rice', 'onion', 'garlic', 'tomato', 'tomatoes', 'potato', 'potatoes', 'carrot', 'carrots', 'cucumber',
    'lettuce', 'spinach', 'avocado', 'lemon', 'lime', 'banana', 'apple', 'pepper', 'peppers', 'chili', 'ginger',
    'spice', 'spices', 'curry', 'biryani', 'masala', 'seasoning', 'oil', 'olive oil', 'pasta', 'spaghetti', 'macaroni',
    'noodle', 'noodles', 'bread', 'bun', 'buns', 'toast', 'pita', 'chickpea', 'chickpeas', 'lentil', 'lentils',
    'bean', 'beans', 'egg', 'eggs', 'flour', 'butter', 'cheese', 'mozzarella', 'cheddar', 'yogurt', 'milk',
    'cream', 'sauce', 'vinegar', 'mustard', 'mayo', 'mayonnaise', 'ketchup', 'salt', 'sugar', 'honey'
]

INGREDIENT_MODIFIERS_AND_UNITS = {
    'medium', 'small', 'large', 'big', 'mini', 'jumbo', 'fresh', 'organic', 'low-fat', 'non-fat',
    'whole', 'canned', 'sliced', 'packet', 'pack', 'cups', 'cup', 'tbsp', 'tsp', 'tablespoon',
    'teaspoon', 'clove', 'cloves', 'head', 'heads', 'slice', 'slices', 'jar', 'jars', 'can', 'cans',
    'bottle', 'bottles', 'box', 'boxes', 'bag', 'bags', 'bunch', 'bunches', 'pinch', 'pinches',
    'diced', 'chopped', 'minced', 'grated', 'shredded', 'peeled', 'crushed', 'ground', 'boneless',
    'skinless', 'ripe', 'dry', 'dried', 'frozen', 'cooked', 'raw', 'pieces', 'piece', 'pcs',
    'grams', 'gram', 'approx', 'of', 'for', 'flavor', 'flavoured', 'flavored', 'style', 'type',
    'red', 'white', 'brown', 'yellow', 'green', 'black', 'blue', 'gold', 'golden', 'extra',
    'grand', 'long', 'pure', 'original', 'special', 'hot', 'cold', 'super', 'new', 'best',
    'classic', 'premium', 'deluxe', 'fine', 'grade', 'light', 'mild', '1l', '2l', '500ml', '250ml',
    '5kg', '2kg', '1kg', '500g', '700g', '100g', '60g', '300g', '400g', '200g'
}

def clean_ingredient_phrase(ing: str) -> str:
    """Strips quantities, units, and non-essential modifiers to yield the core ingredient phrase."""
    import re
    if not ing:
        return ""
    txt = ing.strip().lower()
    txt = normalize_term(txt)
    # Strip leading quantities and units (e.g. '300g ', '1 medium ', '2 tbsp ', '1/2 cup ')
    txt = re.sub(r'^\d+(\.\d+)?(/\d+)?\s*(g|kg|ml|l|slices?|pcs?|pieces?|heads?|cups?|tbsp|tsp|tablespoons?|teaspoons?|cloves?|grams?|pack|packet|box|can|jar|bottle)?\s*', '', txt).strip()
    words = [w for w in txt.split() if w not in INGREDIENT_MODIFIERS_AND_UNITS and not w.isdigit()]
    return ' '.join(words) if words else txt

def is_semantically_relevant_for_ingredient(product: dict, ingredient_raw: str) -> bool:
    """Validates that a product is genuinely relevant to an ingredient, blocking cross-category contamination."""
    if not product:
        return False
    p_name = (product.get('name') or '').lower()
    p_subcat = (product.get('subcategory') or '').lower()
    p_cat = (product.get('category') or '').lower()
    ing = (ingredient_raw or '').lower()
    
    # 1. Exclude bulk industrial packaging
    if any(b in p_name for b in ['40kg', '25kg', '20kg', '10kg', '40 kg', '25 kg', '20 kg', '10 kg']):
        return False
        
    # 2. Exclude non-food categories, cosmetics, flowers, plants, and cleaning supplies
    if p_cat in ('household', 'baby', 'pet'):
        return False
    non_food_words = ['shampoo', 'night cream', 'face cream', 'body scrub', 'shower gel', 'lotion', 'deodorant', 'soap', 'detergent', 'cleaner', 'wash', 'hair', 'flower', 'flowers', 'arrangement', 'bouquet', 'plant']
    if any(c in p_name for c in non_food_words) or 'skin & body' in p_subcat or 'hair care' in p_subcat or 'hygiene' in p_subcat or 'flowers' in p_subcat:
        return False
        
    # 3. Exclude desserts/cakes from savory recipes
    savory_staples = [
        'chicken', 'beef', 'lamb', 'meat', 'rice', 'onion', 'garlic', 'tomato', 'potato',
        'carrot', 'cucumber', 'lettuce', 'spinach', 'vegetable', 'spice', 'curry', 'biryani',
        'pepper', 'salt', 'oil', 'olive oil', 'pasta', 'spaghetti', 'noodle', 'bread', 'bun',
        'chickpea', 'lentil', 'bean', 'egg', 'flour', 'butter', 'cheese', 'yogurt', 'milk', 'salad', 'greens'
    ]
    dessert_words = ['cake', 'cookie', 'biscuit', 'chocolate', 'candy', 'sweet', 'wafer', 'muffin', 'brownie', 'pastry', 'donut', 'red velvet', 'pudding', 'smoothie']
    if any(s in ing for s in savory_staples):
        if any(d in p_name for d in dessert_words) and not any(d in ing for d in dessert_words):
            return False
            
    # 4. Exclude canned fish/seafood from non-seafood recipes
    if any(s in p_name for s in ['sardine', 'anchov', 'tuna', 'mackerel']):
        if not any(s in ing for s in ['sardine', 'anchov', 'tuna', 'fish', 'seafood']):
            return False
            
    # 5. Exclude mixed nuts from non-nut recipes
    if ('mixed' in p_name and 'nut' in p_name) or ('deluxe nut' in p_name):
        if not any(n in ing for n in ['nut', 'almond', 'cashew', 'peanut', 'walnut']):
            return False
            
    # 6. Exclude drinks/sodas when ingredient is a fresh produce fruit/vegetable (e.g. lemon, lime)
    if any(f in ing for f in ['lemon', 'lime', 'orange', 'apple', 'banana']) and p_cat in ('beverages',):
        if not any(d in ing for d in ['drink', 'juice', 'soda', 'beverage']):
            return False

    # 7. Sliced Bread / Sandwich Bread Guard: Exclude breadcrumbs, breadsticks, croutons
    if any(b in ing for b in ['bread', 'slice', 'bun', 'toast', 'loaf', 'sandwich']):
        if any(ex in p_name for ex in ['crumbs', 'breading', 'breadstick', 'crouton', 'bread bin', 'crumb', 'sticks']) and 'crumb' not in ing:
            return False

    # 8. Lemon / Citrus / Juice Guard: Exclude dessert jelly, gelatin, custard, candy
    if any(c in ing for c in ['lemon', 'lime', 'citrus']):
        if any(ex in p_name for ex in ['jelly', 'gelatin', 'dessert', 'pudding', 'custard', 'candy', 'tea bag', 'sachet']) and 'jelly' not in ing and 'dessert' not in ing:
            return False

    # 9. Salad Greens Guard: Exclude pastries (fatayer, samosas), cookies, chips
    if any(g in ing for g in ['salad', 'greens', 'lettuce', 'spinach', 'mixed greens']):
        if any(ex in p_name for ex in ['fatayer', 'pastry', 'samosa', 'croissant', 'pie', 'puff', 'cookie', 'biscuit', 'chips', 'crisp']) and 'fatayer' not in ing and 'pastry' not in ing:
            return False

    # 10. Pizza Dough / Crust Guard: Exclude ready-made mini cooked pizzas / toppings
    if any(d in ing for d in ['pizza dough', 'dough', 'crust', 'pizza base']):
        if any(ex in p_name for ex in ['pizza vegetable', 'pizza topping', 'frozen pizza', 'cooked pizza', 'box set']) and 'vegetable' not in ing:
            return False

    # 11. Cooking Oil Guard: Exclude Dairy (cheese/butter) and snacks (chips/sticks)
    if any(o in ing for o in ['oil', 'vegetable oil', 'olive oil', 'cooking oil', 'sunflower oil', 'corn oil']):
        if p_cat in ('dairy', 'snacks', 'bakery') or any(ex in p_name for ex in ['cheese', 'feta', 'butter', 'stick', 'crisp', 'chips', 'cracker']):
            return False

    # 12. Spice / Seasoning / Powder Guard: Exclude Snacks (energy mix, nut mix, trail mix) and dried fruits
    if any(s in ing for s in ['spice', 'masala', 'curry powder', 'biryani spice', 'turmeric', 'cumin', 'paprika', 'coriander', 'cinnamon', 'powder']):
        if p_cat in ('snacks', 'beverages', 'produce') or any(ex in p_name for ex in ['energy mix', 'trail mix', 'nut mix', 'dried fruit', 'fruit', 'bar', 'biscuit', 'cookie', 'snack']):
            return False

    # 13. Mixed Vegetables / Fresh Veg Guard: Exclude dried fruits and snack sticks
    if any(v in ing for v in ['vegetables', 'mixed vegetables', 'veggies', 'mixed veg']):
        if p_cat in ('snacks', 'bakery') or any(ex in p_name for ex in ['dried fruit', 'fruit', 'snack', 'stick', 'chip', 'crisp', 'biscuit', 'cookie']):
            return False

    # 14. Rice / Grain Guard: Exclude non-grain snacks
    if any(r in ing for r in ['rice', 'basmati', 'jasmine rice', 'grain']):
        if p_cat not in ('pantry/grains', 'produce') or any(ex in p_name for ex in ['cooker', 'cracker', 'cake', 'biscuit', 'chips']):
            return False

    # 15. Plain Pasta / Spaghetti / Macaroni Guard: Exclude meat-filled tortellini/ravioli, sauces, and snacks
    if any(p in ing for p in ['pasta', 'spaghetti', 'macaroni', 'noodle', 'penne', 'fusilli', 'vermicelli']):
        if not any(m in ing for m in ['beef', 'meat', 'chicken', 'pork', 'lamb']):
            if any(ex in p_name for ex in ['beef', 'angus', 'chicken', 'meat', 'pork', 'bacon', 'ham', 'pretzel', 'hummus', 'tortellini', 'ravioli']):
                return False
        if not any(s in ing for s in ['sauce', 'bolognese', 'marinara']):
            if any(ex in p_name for ex in ['pasta sauce', 'pizza sauce', 'sauce for']):
                return False
            
    # 16. Exclude cooking appliances
    if any(a in p_name for a in ['cooker', 'scooper', 'appliance', 'knife', 'pan', 'pot', 'scale']):
        return False
        
    return True

def map_ingredients_to_skus(ingredient_list):
    """
    Fuzzy/simple string mapping of ingredients to product SKUs.
    Returns dict mapping ingredient_name -> product_dict or None.
    Excludes non-food categories and verifies semantic relevance.
    """
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    mapping = {}
    for ing in ingredient_list:
        clean_ing = clean_ingredient_phrase(ing)
        
        # 1. Try exact match first
        cursor.execute("SELECT p.*, i.stock_qty FROM products p JOIN inventory i ON p.sku = i.sku WHERE LOWER(p.name) = ? AND i.stock_qty > 0 LIMIT 1", (clean_ing,))
        row = cursor.fetchone()
        match = row if row and is_semantically_relevant_for_ingredient(row, ing) else None
        
        # 2. Try full clean phrase search
        if not match:
            cursor.execute("""
                SELECT p.*, i.stock_qty FROM products p
                JOIN inventory i ON p.sku = i.sku
                WHERE (LOWER(p.name) LIKE ? OR LOWER(p.subcategory) LIKE ? OR LOWER(p.brand) LIKE ?)
                  AND p.category NOT IN ('Household', 'Baby', 'Pet')
                  AND i.stock_qty > 0
                ORDER BY
                  CASE 
                    WHEN p.category = 'Pantry/Grains' AND p.subcategory = 'Pastas' AND LOWER(p.name) NOT LIKE '%sauce%' AND LOWER(p.name) NOT LIKE '%beef%' AND ? IN ('pasta', 'spaghetti', 'macaroni', 'noodle') THEN 0
                    WHEN LOWER(p.name) = ? THEN 1
                    WHEN LOWER(p.name) LIKE ? THEN 2
                    WHEN p.category = 'Produce' AND ? IN ('onion', 'tomato', 'tomatoes', 'garlic', 'lettuce', 'cucumber', 'spinach', 'potato', 'carrot', 'salad greens', 'salad') THEN 3
                    WHEN p.category = 'Pantry/Grains' AND ? IN ('olive oil', 'oil', 'rice', 'spice', 'biryani', 'pasta', 'spaghetti', 'flour') THEN 3
                    WHEN p.category = 'Meat & Seafood' AND ? IN ('chicken', 'beef', 'lamb', 'meat', 'fish', 'turkey', 'pepperoni') THEN 3
                    WHEN p.category = 'Dairy' AND ? IN ('cheese', 'yogurt', 'milk', 'butter', 'mozzarella') THEN 3
                    WHEN p.category = 'Bakery' AND ? IN ('bread', 'bun', 'buns', 'toast', 'pita', 'sliced bread', 'dough') THEN 3
                    ELSE 4
                  END,
                  i.stock_qty DESC
                LIMIT 20
            """, (f'%{clean_ing}%', f'%{clean_ing}%', f'%{clean_ing}%', clean_ing, clean_ing, f'{clean_ing}%', clean_ing, clean_ing, clean_ing, clean_ing, clean_ing))
            for cand in cursor.fetchall():
                if is_semantically_relevant_for_ingredient(cand, ing):
                    match = cand
                    break
                    
        # 3. Try token fallback (prioritizing recognized food nouns)
        if not match:
            tokens = [w for w in clean_ing.split() if len(w) > 2]
            tokens.sort(key=lambda t: 0 if t in FOOD_NOUNS_LIST else 1)
            for t in tokens:
                cursor.execute("""
                    SELECT p.*, i.stock_qty FROM products p
                    JOIN inventory i ON p.sku = i.sku
                    WHERE (LOWER(p.name) LIKE ? OR LOWER(p.subcategory) LIKE ? OR LOWER(p.brand) LIKE ?)
                      AND p.category NOT IN ('Household', 'Baby', 'Pet')
                      AND i.stock_qty > 0
                    ORDER BY
                      CASE 
                        WHEN p.category = 'Pantry/Grains' AND p.subcategory = 'Pastas' AND LOWER(p.name) NOT LIKE '%sauce%' AND LOWER(p.name) NOT LIKE '%beef%' AND ? IN ('pasta', 'spaghetti', 'macaroni', 'noodle') THEN 0
                        WHEN LOWER(p.name) = ? THEN 1
                        WHEN LOWER(p.name) LIKE ? THEN 2
                        WHEN p.category = 'Produce' AND ? IN ('onion', 'tomato', 'tomatoes', 'garlic', 'lettuce', 'cucumber', 'spinach', 'potato', 'carrot', 'salad', 'greens') THEN 3
                        WHEN p.category = 'Meat & Seafood' AND ? IN ('chicken', 'beef', 'lamb', 'meat', 'fish', 'turkey', 'pepperoni') THEN 3
                        WHEN p.category = 'Pantry/Grains' AND ? IN ('olive oil', 'oil', 'rice', 'pasta', 'spaghetti', 'spice', 'biryani', 'curry', 'flour') THEN 3
                        WHEN p.category = 'Dairy' AND ? IN ('cheese', 'yogurt', 'milk', 'butter', 'mozzarella') THEN 3
                        WHEN p.category = 'Bakery' AND ? IN ('bread', 'bun', 'buns', 'toast', 'pita', 'dough') THEN 3
                        ELSE 4
                      END,
                      i.stock_qty DESC
                    LIMIT 20
                """, (f'%{t}%', f'%{t}%', f'%{t}%', t, t, f'{t}%', t, t, t, t, t))
                for cand in cursor.fetchall():
                    if is_semantically_relevant_for_ingredient(cand, ing):
                        match = cand
                        break
                if match:
                    break
                    
        mapping[ing] = match
        
    conn.close()
    return mapping

def get_customer_recommendations(customer_id, category=None, channel='online', in_stock_only=True):
    """
    Personalized recommendations for a customer.
    Applies customer preferences (allergies, diets) as strict filters.
    Ranks products by customer's purchase frequency, filtered by in-stock inventory.
    """
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    # 1. Fetch customer details
    cursor.execute("SELECT name, preferences_json FROM customers WHERE customer_id = ?", (customer_id,))
    cust = cursor.fetchone()
    if not cust:
        conn.close()
        return []
        
    prefs = json.loads(cust['preferences_json'])
    diet = prefs.get('diet', 'none')
    allergies = prefs.get('allergies', [])
    
    # 2. Get customer's purchase counts per SKU
    cursor.execute(
        """
        SELECT sku, COUNT(*) as buy_count 
        FROM purchase_history 
        WHERE customer_id = ? 
        GROUP BY sku
        """,
        (customer_id,)
    )
    purchase_counts = {row['sku']: row['buy_count'] for row in cursor.fetchall()}
    
    # 3. Fetch candidate products (optionally in category) that are in stock
    query = """
        SELECT p.*, i.stock_qty, i.channel 
        FROM products p
        JOIN inventory i ON p.sku = i.sku
        WHERE i.channel = ?
    """
    params = [channel]
    if in_stock_only:
        query += " AND i.stock_qty > 0"
    if category:
        query += " AND p.category = ?"
        params.append(category)
        
    cursor.execute(query, params)
    candidates = cursor.fetchall()
    conn.close()
    
    # 4. Filter and rank candidates in Python based on preferences
    recommended = []
    for p in candidates:
        attr = p.get('attributes_json', {})
        
        # Apply diet filters
        if diet == 'low-fat' and attr.get('fat_content') not in ('low-fat', 'non-fat'):
            # If it's dairy, we require low fat. For produce, it's naturally low-fat.
            if p['category'] == 'Dairy':
                continue
        elif diet == 'vegan' and attr.get('vegan') is False:
            continue
        elif diet == 'gluten-free' and attr.get('gluten_free') is False:
            continue
            
        # Apply allergy filters
        has_allergy = False
        for allergy in allergies:
            if allergy == 'nuts' and 'almond' in p['name'].lower():
                has_allergy = True
                break
            if allergy == 'dairy' and attr.get('dairy_free') is False:
                has_allergy = True
                break
        if has_allergy:
            continue
            
        # Score the product: purchases boost score, matching favorite category boosts score
        buy_count = purchase_counts.get(p['sku'], 0)
        fav_categories = prefs.get('favorite_categories', [])
        fav_boost = 2 if p['category'] in fav_categories else 0
        
        p['score'] = buy_count + fav_boost
        recommended.append(p)
        
    # Sort by score desc, price asc
    recommended.sort(key=lambda x: (-x['score'], x['price']))
    
    # Return top 5 recommendations
    return recommended[:5]

def get_affinity(sku_list, top_n=3, channel='online', in_stock_only=True):
    """
    Get recommended affinity products (cross-sells) based on a list of SKUs.
    Looks up precomputed rules in the affinity table and falls back to category-level
    cross-sells if precomputed rules yield fewer than top_n products.
    """
    if not sku_list:
        return []
        
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    placeholders = ",".join("?" for _ in sku_list)
    query = f"""
        SELECT a.sku_b as sku, MAX(a.confidence_score) as confidence
        FROM affinity a
        JOIN inventory i ON a.sku_b = i.sku
        WHERE a.sku_a IN ({placeholders}) 
          AND a.sku_b NOT IN ({placeholders})
          AND i.channel = ?
    """
    params = list(sku_list) + list(sku_list) + [channel]
    
    if in_stock_only:
        query += " AND i.stock_qty > 0"
        
    query += f"""
        GROUP BY a.sku_b
        ORDER BY confidence DESC
        LIMIT ?
    """
    params.append(top_n)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    existing_skus = set(sku_list)
    result_skus_set = set()
    rows_skus = []
    conf_map = {}
    
    for r in rows:
        result_skus_set.add(r['sku'])
        rows_skus.append(r['sku'])
        conf_map[r['sku']] = r['confidence']
        
    # If precomputed rules yielded fewer than top_n products, perform intelligent category cross-sell fallback
    if len(rows_skus) < top_n:
        cursor.execute(f"SELECT DISTINCT category, subcategory FROM products WHERE sku IN ({placeholders})", list(sku_list))
        cats_info = cursor.fetchall()
        input_cats = {r['category'] for r in cats_info if r.get('category')}
        
        CROSS_SELL_MAP = {
            "Produce": ["Pantry/Grains", "Dairy", "Produce"],
            "Dairy": ["Bakery", "Dairy", "Pantry/Grains"],
            "Bakery": ["Dairy", "Pantry/Grains", "Beverages"],
            "Meat & Seafood": ["Pantry/Grains", "Produce", "Dairy"],
            "Pantry/Grains": ["Produce", "Dairy", "Meat & Seafood"],
            "Snacks": ["Beverages", "Snacks"],
            "Beverages": ["Snacks", "Beverages"],
            "Pet": ["Pet"],
            "Baby": ["Baby"],
            "Household": ["Household"],
        }
        
        target_cats = []
        for cat in input_cats:
            target_cats.extend(CROSS_SELL_MAP.get(cat, ["Produce", "Pantry/Grains", "Dairy"]))
        if not target_cats:
            target_cats = ["Produce", "Pantry/Grains", "Dairy"]
            
        target_cat_placeholders = ",".join("?" for _ in target_cats)
        all_excluded = list(existing_skus | result_skus_set)
        exclude_placeholders = ",".join("?" for _ in all_excluded)
        
        is_food_input = any(c not in ('Household', 'Baby', 'Pet') for c in input_cats)
        exc_cat_sql = " AND p.category NOT IN ('Household', 'Baby', 'Pet')" if is_food_input else ""
        
        fb_query = f"""
            SELECT p.*, i.stock_qty, i.channel 
            FROM products p
            JOIN inventory i ON p.sku = i.sku AND i.channel = ?
            WHERE p.category IN ({target_cat_placeholders})
              AND p.sku NOT IN ({exclude_placeholders})
              AND p.price > 0.0 {exc_cat_sql}
        """
        fb_params = [channel] + target_cats + all_excluded
        if in_stock_only:
            fb_query += " AND i.stock_qty > 0"
            
        fb_query += """
            ORDER BY 
                CASE 
                    WHEN p.subcategory IN ('Fresh Vegetables', 'Fresh Fruit', 'Fruit & Vegetables', 'Fresh Produce', 'Cooking & Baking', 'Spices & Seasonings', 'Sauces', 'Dairy') THEN 0
                    WHEN p.subcategory != 'Uncategorized' THEN 1
                    ELSE 2
                END,
                i.stock_qty DESC
            LIMIT ?
        """
        fb_params.append(top_n - len(rows_skus))
        
        cursor.execute(fb_query, fb_params)
        fb_rows = cursor.fetchall()
        
        # Compute rough relevance confidence based on category match
        input_subcats = {r['subcategory'] for r in cats_info if r.get('subcategory')}
        for fb in fb_rows:
            rows_skus.append(fb['sku'])
            # Higher confidence if subcategory matches an input subcategory
            fb_subcat = fb.get('subcategory', '')
            fb_cat = fb.get('category', '')
            if fb_subcat in input_subcats:
                conf = 0.85
            elif fb_cat in input_cats:
                conf = 0.70
            else:
                conf = 0.55
            conf_map[fb['sku']] = conf
            
    if not rows_skus:
        conn.close()
        return []
        
    skus_placeholders = ",".join("?" for _ in rows_skus)
    cursor.execute(
        f"SELECT * FROM products WHERE sku IN ({skus_placeholders})",
        rows_skus
    )
    products = cursor.fetchall()
    conn.close()
    
    for p in products:
        p['confidence'] = conf_map.get(p['sku'], 0.75)
        
    products.sort(key=lambda x: -x['confidence'])
    return products

def get_customer_profile(customer_id):
    """
    Tier 1 personalization tool. Returns general profile preferences.
    """
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT preferences_json FROM customers WHERE customer_id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {
            "dietary_preference": "none",
            "preferred_brands": [],
            "avoid_list": []
        }
        
    try:
        prefs = json.loads(row['preferences_json'])
    except Exception:
        prefs = {}
        
    return {
        "dietary_preference": prefs.get("diet", "none"),
        "preferred_brands": prefs.get("preferred_brands", []),
        "avoid_list": prefs.get("allergies", [])
    }

