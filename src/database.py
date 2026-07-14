import sqlite3
import json
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db", "mvp_demo.db"))

def get_connection():
    return sqlite3.connect(DB_PATH)

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

def search_products(category=None, query_str=None, attributes=None, price_max=None, channel='online', raw_query=None, limit=None):
    """
    Search products based on category, query text, attributes, and max price.
    Also returns stock info for the specified channel.
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
    
    if category:
        query += " AND p.category = ?"
        params.append(category)
        
    if query_str or raw_query:
        term_filters = []
        if query_str:
            term_filters.append("(p.name LIKE ? OR p.subcategory LIKE ? OR p.brand LIKE ?)")
            # Normalize spelling variations (e.g. briyani -> biryani)
            norm_query = query_str.lower().replace("briyani", "biryani").replace("spageti", "spaghetti")
            term = f"%{norm_query}%"
            params.extend([term, term, term])
        if raw_query:
            term_filters.append("(p.name LIKE ? OR p.subcategory LIKE ? OR p.brand LIKE ?)")
            norm_raw = raw_query.lower().replace("briyani", "biryani").replace("spageti", "spaghetti")
            term = f"%{norm_raw}%"
            params.extend([term, term, term])
        query += " AND (" + " OR ".join(term_filters) + ")"
        
    if price_max:
        query += " AND p.price <= ?"
        params.append(price_max)
        
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        
    cursor.execute(query, params)
    products = cursor.fetchall()
    conn.close()
    
    # Filter by attributes_json in python to keep SQL simple
    if attributes:
        filtered = []
        for p in products:
            match = True
            p_attr = p.get('attributes_json', {})
            for k, v in attributes.items():
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
            WHERE p.category = ? AND p.sku != ?
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
    """
    cursor.execute(query, list(sku_list))
    offers = cursor.fetchall()
    conn.close()
    return offers

def map_ingredients_to_skus(ingredient_list):
    """
    Fuzzy/simple string mapping of ingredients (e.g. 'spaghetti') to product SKUs.
    Returns dict mapping ingredient_name -> product_dict or None.
    """
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    mapping = {}
    for ing in ingredient_list:
        clean_ing = ing.strip().lower()
        
        # 1. Try exact match first
        cursor.execute("SELECT * FROM products WHERE LOWER(name) = ?", (clean_ing,))
        row = cursor.fetchone()
        if row:
            mapping[ing] = row
            continue
            
        # 2. Stop words removal for fuzzy fallback
        for stop_word in ['fresh', 'organic', 'low-fat', 'whole', 'canned', 'sliced']:
            clean_ing = clean_ing.replace(stop_word, '').strip()
        # Collapse multiple spaces left after stop words removal
        clean_ing = " ".join(clean_ing.split())
            
        cursor.execute(
            """
            SELECT p.* FROM products p
            WHERE LOWER(p.name) LIKE ? OR LOWER(p.subcategory) LIKE ? OR LOWER(p.category) LIKE ?
            ORDER BY 
                CASE 
                    WHEN LOWER(p.name) = ? THEN 1
                    WHEN LOWER(p.name) LIKE ? THEN 2
                    ELSE 3
                END
            LIMIT 1
            """,
            (f"%{clean_ing}%", f"%{clean_ing}%", f"%{clean_ing}%", clean_ing, f"{clean_ing}%")
        )
        row = cursor.fetchone()
        mapping[ing] = row if row else None
        
    conn.close()
    return mapping

def get_customer_recommendations(customer_id, category=None, query_str=None, channel='online', in_stock_only=True):
    """
    Personalized recommendations for a customer.
    Applies customer preferences (allergies, diets) as strict filters.
    Ranks products by customer's purchase frequency, filtered by in-stock inventory.
    Biased by active search query terms for relevance, falling back to category.
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
    
    # 3. Fetch candidate products matching active query terms if provided
    candidates = []
    if query_str:
        words = [w.strip("()?.!,;") for w in query_str.lower().split()]
        # Remove common stopwords to get clean keywords
        stop_words = {"need", "want", "i", "get", "find", "search", "show", "me", "some", "recipe", "how", "make", "cook", "to", "for", "with"}
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        
        # Apply spelling corrections to extracted keywords
        normalized_keywords = []
        for kw in keywords:
            norm_kw = kw.replace("briyani", "biryani").replace("spageti", "spaghetti")
            normalized_keywords.append(norm_kw)
        
        if normalized_keywords:
            query = """
                SELECT p.*, i.stock_qty, i.channel 
                FROM products p
                JOIN inventory i ON p.sku = i.sku
                WHERE i.channel = ?
            """
            params = [channel]
            if in_stock_only:
                query += " AND i.stock_qty > 0"
                
            like_clauses = " OR ".join("(LOWER(p.name) LIKE ? OR LOWER(p.subcategory) LIKE ?)" for _ in normalized_keywords)
            query += f" AND ({like_clauses})"
            for kw in normalized_keywords:
                params.append(f"%{kw}%")
                params.append(f"%{kw}%")
                
            cursor.execute(query, params)
            candidates = cursor.fetchall()
            
    # Fallback to category if no keyword candidates found, or get all candidates if neither is specified
    if not candidates:
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
    Looks up precomputed rules in the affinity table and filters by stock.
    """
    if not sku_list:
        return []
        
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    placeholders = ",".join("?" for _ in sku_list)
    # Find sku_b where sku_a is in the list, and sku_b is not in the list (don't suggest what is already in cart)
    # Join with inventory to filter by channel and stock
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
    
    if not rows:
        conn.close()
        return []
        
    # Retrieve product details for the affinity SKUs
    affinity_skus = [row['sku'] for row in rows]
    skus_placeholders = ",".join("?" for _ in affinity_skus)
    
    cursor.execute(
        f"SELECT * FROM products WHERE sku IN ({skus_placeholders})",
        affinity_skus
    )
    products = cursor.fetchall()
    conn.close()
    
    # Map confidence back to products
    conf_map = {row['sku']: row['confidence'] for row in rows}
    for p in products:
        p['confidence'] = conf_map.get(p['sku'], 0.0)
        
    # Sort products by confidence descending
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

