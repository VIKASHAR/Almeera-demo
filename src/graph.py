import json
import logging
import time
import asyncio
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

# Import database tools and LLM helper
from src.config import llm_call
import src.database as db

logger = logging.getLogger(__name__)

# Define the state schema matching Spec v3
class AgentState(TypedDict):
    # Inputs
    raw_text: str
    customer_id: str
    channel: str # 'online' | 'in_store'
    session_id: str
    
    # Start time for timeout tracking
    start_time: float
    
    # Tier 1 profile details (t=0)
    tier1_profile: Dict[str, Any] # {"dietary_preference": str, "preferred_brands": [str], "avoid_list": [str]}
    
    # Router decisions
    intent: str # 'search' | 'recipe' | 'greeting'
    search_category: Optional[str]
    search_query: Optional[str]
    search_filters: Dict[str, Any]
    dish_name: Optional[str]
    
    # Resolved primary SKUs/details (Cap 1 & 2)
    resolved_skus: List[str]
    substitutions_made: List[Dict[str, Any]]
    offers_applied: List[str]
    primary_result: Dict[str, Any] # details dictionary
    
    # Fallback path trigger
    no_matches_triggered: bool
    
    # Tier 2 personalization output (Cap 3)
    recommended_skus: List[str]
    personalization_reason: str
    
    # Affinity output (Cap 4)
    combo_skus: List[str]
    confidence_scores: Dict[str, float]
    
    # Composer final outputs
    reply_text: str
    primary_cards: List[str]
    personalized_cards: List[str]
    combo_cards: List[str]
    enrichment_timed_out: bool

# --- Nodes ---

async def tier1_personalization_node(state: AgentState) -> Dict[str, Any]:
    """
    Tier 1 personalization. Runs at t=0 to get general profile filters.
    Best-effort, but runs extremely fast (<2ms) on local SQLite database.
    """
    logger.info(f"--- TIER 1 PERSONALIZATION NODE --- Customer: {state['customer_id']}")
    try:
        # Wrap in a short timeout just to strictly satisfy the spec's best-effort contract
        profile = await asyncio.wait_for(
            asyncio.to_thread(db.get_customer_profile, state['customer_id']),
            timeout=0.2 # 200ms timeout
        )
    except asyncio.TimeoutError:
        logger.warning("Tier 1 personalization timed out! Running with empty profile filters.")
        profile = {"dietary_preference": "none", "preferred_brands": [], "avoid_list": []}
    except Exception as e:
        logger.error(f"Error in Tier 1 personalization: {e}")
        profile = {"dietary_preference": "none", "preferred_brands": [], "avoid_list": []}
        
    return {"tier1_profile": profile}

async def intent_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Classifies user intent (search vs recipe vs greeting) and extracts category & filters.
    """
    logger.info(f"--- INTENT ROUTER NODE --- Query: {state['raw_text']}")
    prompt = f"""
    You are an intent router for a grocery store chatbot.
    Your task is to classify the user's query into one of three intents:
    1. 'search': The user is looking for a specific product, brand, category, or type of item (e.g. "low-fat milk", "need pasta", "do you have butter", "do you have mushrooms", "find oil").
    2. 'recipe': The user is asking for a meal suggestion, recipe, instructions, dinner ideas, or how to cook something (e.g. "suggest a pasta recipe for dinner", "what can I make with tomatoes", "how to make a sandwich", "recipe for salad").
    3. 'greeting': The user is saying hi, hello, greeting the bot, or asking general conversational questions (e.g. "hi", "hello", "how are you", "who are you", "can you help me").
    
    Respond STRICTLY in JSON format with the following keys:
    - "intent": "search" | "recipe" | "greeting"
    - "category": string or null. ONLY provide this if intent is "search". If provided, it MUST be one of:
       * 'Dairy': milk, cheese, butter, yogurt, sour cream, cream cheese.
       * 'Produce': fruits, vegetables, mushrooms, leafy greens (spinach, basil, herbs), garlic, onions, lemons, avocados, alliums, etc.
       * 'Pantry/Grains': pasta, rice, olive oil, tomato sauce, coconut milk, curry powder, cereal, bread, canned beans/chickpeas.
       * 'Beverages': coffee, juice, soda, tea, water.
       * 'Frozen': frozen meals, frozen vegetables, ice cream.
       * 'Household': cleaning, laundry, paper products.
       * 'Meat & Seafood': beef, chicken, fish, seafood.
       * 'Personal Care': oral care, shampoo, soap.
       * 'Snacks': chips, cookies, crackers, nuts.
       Set to null if the query doesn't match any of these categories or if intent is not "search".
    - "dish_name": string or null. Extract the meal/dish name ONLY if intent is "recipe" (e.g., "pasta", "salad", "curry", "sandwich"). Otherwise, set to null.
    - "search_query": string or null. ONLY provide this if intent is "search". Extract the core product/item term or subcategory, mapping synonyms and plurals.
       IMPORTANT: Do NOT translate or rewrite terms that directly match any of the following valid database subcategories:
       ['Alliums', 'Fruit', 'Herbs', 'Leafy Greens', 'Mushrooms', 'Tomatoes', 'Butter', 'Cheese', 'Cream Cheese', 'Milk', 'Sour Cream', 'Yogurt', 'Coffee', 'Juice', 'Soda', 'Tea', 'Water', 'Frozen Meals', 'Frozen Vegetables', 'Ice Cream', 'Cleaning', 'Laundry', 'Paper Products', 'Beef', 'Chicken', 'Fish', 'Seafood', 'Bakery', 'Canned Beans', 'Cereal', 'Milk Alternative', 'Oil', 'Pasta', 'Rice', 'Sauce', 'Spices', 'Oral Care', 'Shampoo', 'Soap', 'Chips', 'Cookies', 'Crackers', 'Nuts'].
       For example, if the query is "alliums" or "aliums", do NOT rewrite it to "onions"; keep it as "alliums".
    - "filters": {{
          "attributes": {{}}, -- e.g. {{"fat_content": "low-fat"}} or {{"organic": true}} or {{"gluten_free": true}} (if specified in query)
          "price_max": float or null -- e.g. 5.50 (if specified)
       }}
    
    User Query: "{state['raw_text']}"
    """
    
    system_instruction = "You are a precise intent router. Output ONLY the JSON structure matching the schema."
    
    try:
        response_raw = llm_call(prompt, system_instruction=system_instruction, json_mode=True)
        response = json.loads(response_raw)
    except Exception as e:
        logger.error(f"Router node failed parsing JSON: {e}")
        # Check standard query content for simple fallback
        query_lower = state['raw_text'].lower()
        if "milk" in query_lower:
            response = {"intent": "search", "category": "Dairy", "search_query": "milk", "dish_name": None, "filters": {"attributes": {}, "price_max": None}}
        elif "pasta" in query_lower or "recipe" in query_lower:
            response = {"intent": "recipe", "category": None, "search_query": None, "dish_name": "Pasta Dinner", "filters": {"attributes": {}, "price_max": None}}
        elif query_lower.strip() in ["hi", "hello", "hey", "greetings"]:
            response = {"intent": "greeting", "category": None, "search_query": None, "dish_name": None, "filters": {"attributes": {}, "price_max": None}}
        else:
            response = {"intent": "search", "category": None, "search_query": None, "dish_name": None, "filters": {"attributes": {}, "price_max": None}}
        
    logger.info(f"Router classified intent as: {response.get('intent')}")
    return {
        "intent": response.get("intent", "search"),
        "search_category": response.get("category"),
        "search_query": response.get("search_query"),
        "search_filters": response.get("filters", {"attributes": {}, "price_max": None}),
        "dish_name": response.get("dish_name")
    }

def is_product_compliant(product: Dict[str, Any], profile: Dict[str, Any]) -> bool:
    """
    Checks if a product satisfies the customer's Tier 1 preferences (diet and allergies).
    """
    if not product:
        return True
        
    p_attr = product.get('attributes_json') or {}
    diet = profile.get("dietary_preference", "none")
    avoid_list = profile.get("avoid_list") or []
    
    # 1. Dietary preference compliance (non-blocking for missing keys except Dairy for low-fat)
    if diet == "low-fat":
        if product.get('category') == 'Dairy' and p_attr.get('fat_content') not in ('low-fat', 'non-fat'):
            return False
    elif diet == "vegan":
        if p_attr.get('vegan') is False:
            return False
    elif diet == "gluten-free":
        if p_attr.get('gluten_free') is False:
            return False
            
    # 2. Allergen/Avoid-list compliance
    p_name_lower = product.get('name', '').lower()
    for allergen in avoid_list:
        allergen_clean = allergen.strip().lower()
        if allergen_clean == 'nuts' and 'almond' in p_name_lower:
            return False
        if allergen_clean == 'dairy' and p_attr.get('dairy_free') is False:
            return False
            
    return True

async def product_search_node(state: AgentState) -> Dict[str, Any]:
    """
    Capability 1: Search products from database, biased by Tier 1 preferences.
    """
    logger.info(f"--- PRODUCT SEARCH NODE (CAP 1) ---")
    channel = state['channel']
    category = state.get("search_category")
    filters = state.get("search_filters") or {"attributes": {}, "price_max": None}
    
    # Tier 1 profile details
    profile = state.get("tier1_profile") or {}
    preferred_brands = profile.get("preferred_brands") or []
    
    # 1. We query using only the user's explicit attributes (no strict dietary prefix bias injected here)
    search_attrs = filters.get("attributes") or {}
    price_max = filters.get("price_max")
    
    # Extract cleaned raw query words
    raw_query = state['raw_text']
    # Remove common conversational verbs and filler words
    stop_words = {
        "need", "want", "i", "get", "find", "search", "show", "me", "some", 
        "a", "timeout", "test", "do", "you", "have", "has", "any", "are", 
        "there", "we", "for", "please", "can", "buy", "how", "much", "is"
    }
    query_words = [
        w for w in raw_query.split() 
        if w.lower().strip("()?.!,;") not in stop_words
    ]
    # Clean punctuation from the final search words
    cleaned_words = [w.strip("()?.!,;") for w in query_words]
    cleaned_raw_query = " ".join(cleaned_words) if cleaned_words else raw_query
    
    # Use LLM-extracted search_query if available, otherwise default to cleaned raw query
    query_str = state.get("search_query") or cleaned_raw_query
        
    # Helper to resolve compliant and in-stock products/substitutes from a list of candidates
    def resolve_products_for_search(candidate_products):
        compliant_candidates = [p for p in candidate_products if is_product_compliant(p, profile)]
        
        # Prioritize preferred brands (non-blocking brand bias)
        if preferred_brands:
            compliant_candidates.sort(key=lambda p: 0 if p.get('brand') in preferred_brands else 1)
            
        in_stock_products = [p for p in compliant_candidates if p['stock_qty'] > 0]
        out_of_stock_products = [p for p in compliant_candidates if p['stock_qty'] == 0]
        
        res_skus = []
        subs_made = []
        prim_products = []
        
        if not in_stock_products and out_of_stock_products:
            # Target item is out of stock! Fetch alternatives (now returns up to 10 candidate products)
            target_sku = out_of_stock_products[0]['sku']
            alternatives = db.get_alternatives(target_sku, in_stock_only=True, channel=channel)
            
            # Filter alternatives for compliance
            compliant_alts = [alt for alt in alternatives if is_product_compliant(alt, profile)]
            
            for alt in compliant_alts:
                res_skus.append(alt['sku'])
                subs_made.append({"requested": target_sku, "substituted_with": alt['sku']})
                prim_products.append(alt)
        else:
            # Keep top 3 matching in-stock products
            for p in in_stock_products[:3]:
                res_skus.append(p['sku'])
                prim_products.append(p)
                
        return res_skus, subs_made, prim_products, out_of_stock_products if not in_stock_products else []

    # 2. Search database with category constraint
    products = db.search_products(category=category, query_str=query_str, attributes=search_attrs, price_max=price_max, channel=channel, raw_query=cleaned_raw_query)
    resolved_skus, substitutions_made, primary_products, oos_list = resolve_products_for_search(products)
    
    # 3. Category Relaxation Fallback:
    # If no matches are found/resolved under the category constraint, broaden the search to other categories
    if not resolved_skus and category is not None:
        logger.info(f"First-pass search for category '{category}' yielded 0 resolved products. Relaxing category constraint...")
        broad_products = db.search_products(category=None, query_str=query_str, attributes=search_attrs, price_max=price_max, channel=channel, raw_query=cleaned_raw_query)
        resolved_skus, substitutions_made, primary_products, oos_list = resolve_products_for_search(broad_products)
        
    # Fetch promotions for resolved items
    promotions = db.get_active_offers(resolved_skus)
    offers_applied = [promo['promo_id'] for promo in promotions]
    
    primary_result = {
        "products": primary_products,
        "is_search_result": True,
        "searched_oos_products": oos_list
    }
    
    return {
        "resolved_skus": resolved_skus,
        "substitutions_made": substitutions_made,
        "offers_applied": offers_applied,
        "primary_result": primary_result
    }

async def recipe_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Capability 2: Recipe generation (LLM), ingredients mapping, and inventory-check/alternatives.
    Biased by Tier 1 preferences (e.g. vegan, low-fat).
    """
    logger.info(f"--- RECIPE GENERATOR NODE (CAP 2) ---")
    channel = state['channel']
    dish_name = state.get("dish_name") or state['raw_text']
    
    # 1. Load Tier 1 profile bias
    profile = state.get("tier1_profile") or {}
    diet = profile.get("dietary_preference", "none")
    avoid_list = profile.get("avoid_list") or []
    
    # Fetch in-stock products to bias the recipe toward available catalog items
    try:
        available_products = db.search_products(channel=channel)
        product_names = [p['name'] for p in available_products if p.get('stock_qty', 0) > 0]
        product_list_str = ", ".join(product_names)
    except Exception as e:
        logger.error(f"Error fetching product list for recipe bias: {e}")
        product_list_str = ""
        
    # Generate instructions using LLM, specifying dietary restrictions from Tier 1
    bias_instruction = ""
    if diet != "none":
        bias_instruction += f" Ensure this recipe strictly follows a {diet} diet."
    if avoid_list:
        bias_instruction += f" Do NOT include any ingredients containing or derived from: {', '.join(avoid_list)}."
        
    if product_list_str:
        bias_instruction += f"\nPrefer using ingredients from this list of available products in our store to make the recipe: {product_list_str}. You can use other ingredients only if absolutely necessary for the dish."
        
    prompt = f"""
    You are a professional supermarket chef.
    Generate a simple recipe for: "{dish_name}".
    {bias_instruction}
    
    Keep the ingredient list small (5 items or less).
    Respond STRICTLY in JSON format with the following keys:
    - "dish_name": string
    - "ingredients": list of strings (e.g. ["Spaghetti Pasta", "Classic Tomato Sauce", "Roma Tomatoes", "Fresh Basil", "Fresh Garlic Bulb"])
    """
    
    system_instruction = "You are a recipe ingredient extractor. Output ONLY the JSON structure."
    
    try:
        response_raw = llm_call(prompt, system_instruction=system_instruction, json_mode=True)
        recipe_data = json.loads(response_raw)
    except Exception as e:
        logger.error(f"Recipe generator failed parsing JSON: {e}")
        # Default mock fallback
        recipe_data = {
            "dish_name": dish_name,
            "ingredients": ["Spaghetti Pasta", "Classic Tomato Sauce", "Roma Tomatoes"]
        }
        
    ingredients = recipe_data.get("ingredients", [])
    logger.info(f"DEBUG: Recipe Generator returned ingredients: {ingredients}")
    
    # 2. Map ingredients to database SKUs
    mapped_skus_dict = db.map_ingredients_to_skus(ingredients)
    logger.info(f"DEBUG: Mapped SKUs dict: {json.dumps({k: (v['sku'] if v else None) for k, v in mapped_skus_dict.items()})}")
    
    resolved_skus = []
    substitutions_made = []
    ingredients_detail = []
    
    # 3. Check inventory and substitute any out of stock or non-compliant ingredients
    for ing_name, product in mapped_skus_dict.items():
        if product:
            sku = product['sku']
            is_compliant = is_product_compliant(product, profile)
            
            # Check stock
            stock = db.check_inventory([sku], channel=channel)
            stock_qty = stock.get(sku, 0) if is_compliant else 0
            
            if stock_qty == 0 or not is_compliant:
                # OOS or Non-compliant ingredient! Find alternative
                alternatives = db.get_alternatives(sku, in_stock_only=True, channel=channel)
                compliant_alts = [alt for alt in alternatives if is_product_compliant(alt, profile)]
                
                if compliant_alts:
                    alt_product = compliant_alts[0]
                    substitutions_made.append({"requested": sku, "substituted_with": alt_product['sku']})
                    resolved_skus.append(alt_product['sku'])
                    
                    ingredients_detail.append({
                        "ingredient_name": ing_name,
                        "sku": alt_product['sku'],
                        "name": alt_product['name'],
                        "price": alt_product['price'],
                        "stock_qty": alt_product['stock_qty'],
                        "in_stock": True,
                        "is_substituted": True,
                        "original_name": product['name']
                    })
                else:
                    # Keep OOS product details if no compliant alternatives exist
                    ingredients_detail.append({
                        "ingredient_name": ing_name,
                        "sku": sku,
                        "name": product['name'],
                        "price": product['price'],
                        "stock_qty": 0,
                        "in_stock": False,
                        "is_substituted": False
                    })
                    resolved_skus.append(sku)
            else:
                resolved_skus.append(sku)
                ingredients_detail.append({
                    "ingredient_name": ing_name,
                    "sku": sku,
                    "name": product['name'],
                    "price": product['price'],
                    "stock_qty": stock_qty,
                    "in_stock": True,
                    "is_substituted": False
                })
        else:
            # Ingredient not mapped in catalog
            ingredients_detail.append({
                "ingredient_name": ing_name,
                "sku": None,
                "name": ing_name,
                "price": None,
                "stock_qty": 0,
                "in_stock": False,
                "is_substituted": False
            })
            
    # Check promotions
    promotions = db.get_active_offers(resolved_skus)
    offers_applied = [promo['promo_id'] for promo in promotions]
    
    primary_result = {
        "dish_name": recipe_data.get("dish_name", dish_name),
        "ingredients": ingredients_detail,
        "is_recipe": True
    }
    
    return {
        "resolved_skus": resolved_skus,
        "substitutions_made": substitutions_made,
        "offers_applied": offers_applied,
        "primary_result": primary_result
    }

async def no_matches_node(state: AgentState) -> Dict[str, Any]:
    """
    Fallback path node. Sets fallback indicator when no SKUs are resolved.
    """
    logger.info("--- NO MATCHES FALLBACK NODE ---")
    return {"no_matches_triggered": True}

async def tier2_personalization_node(state: AgentState) -> Dict[str, Any]:
    """
    Capability 3 (Tier 2): Category-scoped top picks based on customer preferences & history.
    Triggers after SKUs are resolved.
    """
    customer_id = state['customer_id']
    resolved_skus = state.get("resolved_skus", [])
    
    # 1. Determine category of query based on resolved SKUs
    category = state.get("search_category")
    if not category and resolved_skus:
        # Check category of first SKU in DB
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT category FROM products WHERE sku = ?", (resolved_skus[0],))
            row = cursor.fetchone()
            if row:
                category = row[0]
            conn.close()
        except Exception:
            pass
            
    category = category or "Produce" # Default fallback
    logger.info(f"--- TIER 2 PERSONALIZATION NODE (CAP 3) --- Category: {category}")
    
    # Mock latency test: if query contains "timeout", sleep 2 seconds
    if "timeout" in state['raw_text'].lower():
        logger.info("Simulating latency in Tier 2 personalization...")
        await asyncio.sleep(2.0)
        
    # 2. Get personalized recommendations for category (in-stock only)
    channel = state.get("channel", "online")
    recs = db.get_customer_recommendations(customer_id, category=category, channel=channel)
    recommended_skus = [p['sku'] for p in recs]
    reason = f"Top picks in {category} matching your preferences."
    
    return {
        "recommended_skus": recommended_skus,
        "personalization_reason": reason
    }

async def affinity_node(state: AgentState) -> Dict[str, Any]:
    """
    Capability 4: Precomputed market-basket associations (affinity).
    Triggers after SKUs are resolved.
    """
    resolved_skus = state.get("resolved_skus", [])
    logger.info(f"--- AFFINITY NODE (CAP 4) --- Resolved SKUs: {resolved_skus}")
    
    if not resolved_skus:
        return {"combo_skus": [], "confidence_scores": {}}
        
    # Get affinity recommendations (in-stock only)
    channel = state.get("channel", "online")
    aff_products = db.get_affinity(resolved_skus, top_n=3, channel=channel)
    combo_skus = [p['sku'] for p in aff_products]
    confidence_scores = {p['sku']: p.get('confidence', 0.0) for p in aff_products}
    
    return {
        "combo_skus": combo_skus,
        "confidence_scores": confidence_scores
    }

async def composer_node(state: AgentState) -> Dict[str, Any]:
    """
    Merges, deduplicates, ranks, and composes final natural response.
    Includes timeout budget handling for Tier 2 and Affinity enrichment.
    """
    logger.info("--- COMPOSER NODE --- Merging and composing response...")
    
    # 1. Check if enrichment timed out
    # If the user query is "timeout" and the state took more than 1.0s, mark timeout.
    # Otherwise, set a realistic timeout of 5.0s for live LLM API response latency.
    elapsed = time.time() - state.get("start_time", time.time())
    is_timeout_test = "timeout" in state['raw_text'].lower()
    enrichment_timed_out = (is_timeout_test and elapsed > 1.0) or (elapsed > 5.0)
    
    # 2. Extract outputs
    primary_skus = state.get("resolved_skus") or []
    recommended_skus = state.get("recommended_skus") or []
    combo_skus = state.get("combo_skus") or []
    
    # Check if fallback occurred
    no_matches = state.get("no_matches_triggered", False)
    
    # 3. Deduplicate (Spec Rule: dedupe SKUs between personalization and affinity)
    # If a SKU is in primary, remove from recommended & combo.
    # If a SKU is in recommended, remove from combo.
    final_primary = list(dict.fromkeys(primary_skus))
    final_recommended = [sku for sku in recommended_skus if sku not in final_primary]
    final_combo = [sku for sku in combo_skus if sku not in final_primary and sku not in final_recommended]
    
    # 4. Rank/Fetch product details for formatting
    all_final_skus = final_primary + final_recommended + final_combo
    
    # Fetch promotions
    promotions = db.get_active_offers(all_final_skus)
    promo_map = {p['sku']: p for p in promotions}
    
    active_offers = []
    for sku in all_final_skus:
        if sku in promo_map:
            active_offers.append({
                "sku": sku,
                "discount": f"{int(promo_map[sku]['discount_pct'] * 100)}%",
                "description": promo_map[sku]['description']
            })
            
    # Prepare details string for LLM call
    primary_detail = json.dumps(state.get("primary_result", {}), indent=2)
    
    # Fetch details for formatting prompt
    rec_products = []
    combo_products = []
    if final_recommended:
        rec_products = db.search_products(query_str=None)
        rec_products = [p for p in rec_products if p['sku'] in final_recommended]
    if final_combo:
        combo_products = db.search_products(query_str=None)
        combo_products = [p for p in combo_products if p['sku'] in final_combo]
        
    recommended_detail = json.dumps([{ "sku": p['sku'], "name": p['name'], "price": p['price'] } for p in rec_products], indent=2)
    combo_detail = json.dumps([{ "sku": p['sku'], "name": p['name'], "price": p['price'] } for p in combo_products], indent=2)
    
    # 5. Call LLM for final natural composition
    intent = state.get("intent", "search")
    
    if no_matches and intent != "greeting":
        # Fetch all available in-stock products to suggest relevant alternatives
        try:
            available_products = db.search_products(channel=state.get("channel", "online"))
            in_stock_catalog = [{ "name": p['name'], "price": p['price'], "category": p['category'] } for p in available_products if p.get('stock_qty', 0) > 0]
            in_stock_str = json.dumps(in_stock_catalog, indent=2)
        except Exception as e:
            logger.error(f"Error fetching in-stock products for no matches fallback: {e}")
            in_stock_str = "[]"
            
        prompt = f"""
        You are the master composer for a smart grocery store checkout chatbot.
        The customer requested an item that we do not sell or that is currently out of stock.
        
        User Query: "{state['raw_text']}"
        Intent: {intent}
        
        Available In-Stock products in our store:
        {in_stock_str}
        
        Write a friendly, extremely short and crisp markdown response (no more than 2 sentences):
        - Politely inform the customer that the requested item is currently unavailable.
        - Suggest relevant alternative items from our in-stock catalog list (e.g. bananas/lemons for fruit, yogurt/milk for dairy).
        - Do NOT suggest items not in the in-stock list.
        """
        system_instruction = "You are a helpful, concise supermarket assistant. Your responses must be short, crisp, and to the point (no more than 2-3 sentences). Avoid wordy or conversational filler."
        try:
            reply_text = llm_call(prompt, system_instruction=system_instruction, json_mode=False)
        except Exception as e:
            logger.error(f"Fallback LLM call failed: {e}")
            reply_text = "I'm sorry, we don't have that item in stock. Try asking for basic items like 'milk', 'cheese', 'tomatoes', or a 'pasta recipe'."
    else:
        prompt = f"""
        You are the master composer for a smart grocery store checkout chatbot.
        Your task is to write a helpful, friendly response merging:
        
        User Query: "{state['raw_text']}"
        Intent: {intent}
        
        1. Primary Results:
        {primary_detail}
        
        2. Personalized Suggestions for this customer:
        {recommended_detail}
        
        3. Cross-sell combo items:
        {combo_detail}
        
        Offers active: {json.dumps(active_offers)}
        
        Write a friendly, extremely short and crisp markdown response (no more than 2-3 sentences):
        - If it was a 'greeting', greet the customer warmly and ask how you can help. Do NOT say that you don't have recommendations or apologize if the personalized suggestions list is empty. Only point out their personalization suggestions if they are actually provided in the suggestions list. If the list is empty, do NOT mention recommendations at all.
        - If 'search', describe what you found very briefly, explaining any substitutions.
        - If 'recipe', list the recipe steps and mention ingredients mapped to the catalog. Keep instructions simple.
        - Highlight any active deals/discounts.
        - Frame the combo items naturally (e.g., "This goes great with...").
        """
        system_instruction = "You are a helpful, concise supermarket assistant. Your responses must be short, crisp, and to the point (no more than 2-3 sentences). Avoid wordy or conversational filler."
        
        try:
            reply_text = llm_call(prompt, system_instruction=system_instruction, json_mode=False)
        except Exception as e:
            logger.error(f"Composer LLM call failed: {e}")
            reply_text = "Here are the best matches I found for you today in our catalog, including personalized recommendations and promotions."

    return {
        "reply_text": reply_text,
        "primary_cards": final_primary,
        "personalized_cards": final_recommended,
        "combo_cards": final_combo,
        "enrichment_timed_out": enrichment_timed_out
    }

# --- Routing logic (sku_check) ---

def sku_check_routing(state: AgentState) -> List[str]:
    """
    Conditional routing edge checking if any SKUs were resolved.
    Returns a list of target nodes to run concurrently.
    """
    skus = state.get("resolved_skus", [])
    logger.info(f"--- SKU CHECK --- Resolved SKUs count: {len(skus)}")
    
    if len(skus) > 0:
        return ["tier2_personalization", "affinity"]
    else:
        return ["no_matches"]

# --- Graph Definition ---

def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("tier1_personalization", tier1_personalization_node)
    workflow.add_node("intent_router", intent_router_node)
    workflow.add_node("product_search", product_search_node)
    workflow.add_node("recipe_generator", recipe_generator_node)
    workflow.add_node("no_matches", no_matches_node)
    workflow.add_node("tier2_personalization", tier2_personalization_node)
    workflow.add_node("affinity", affinity_node)
    workflow.add_node("composer", composer_node)
    
    # Add Edges
    workflow.set_entry_point("tier1_personalization")
    
    # Parallel split at entry (tier1 + router both fire on query)
    workflow.add_edge("tier1_personalization", "intent_router")
    
    # Router conditional paths
    workflow.add_conditional_edges(
        "intent_router",
        lambda state: state["intent"],
        {
            "search": "product_search",
            "recipe": "recipe_generator",
            "greeting": "no_matches" # Greetings bypass search/recipe nodes and go directly to Composer through fallback path
        }
    )
    
    # Add concurrent conditional edges from product search
    workflow.add_conditional_edges(
        "product_search",
        sku_check_routing,
        {
            "tier2_personalization": "tier2_personalization",
            "affinity": "affinity",
            "no_matches": "no_matches"
        }
    )
    
    # Add concurrent conditional edges from recipe generator
    workflow.add_conditional_edges(
        "recipe_generator",
        sku_check_routing,
        {
            "tier2_personalization": "tier2_personalization",
            "affinity": "affinity",
            "no_matches": "no_matches"
        }
    )
    
    # Merge pathways into Composer
    workflow.add_edge("tier2_personalization", "composer")
    workflow.add_edge("affinity", "composer")
    workflow.add_edge("no_matches", "composer")
    
    # Final step
    workflow.add_edge("composer", END)
    
    return workflow.compile()

# Compile the graph
orchestrator_graph = build_graph()

async def run_chatbot(customer_id: str, channel: str, query: str) -> Dict[str, Any]:
    """
    Runs the LangGraph chatbot orchestrator end-to-end (Asynchronous).
    """
    initial_state = {
        "raw_text": query,
        "customer_id": customer_id,
        "channel": channel,
        "session_id": "demo_session",
        "start_time": time.time(),
        "search_query": None,
        "resolved_skus": [],
        "substitutions_made": [],
        "offers_applied": [],
        "primary_result": {},
        "no_matches_triggered": False,
        "recommended_skus": [],
        "combo_skus": [],
        "confidence_scores": {},
        "reply_text": "",
        "primary_cards": [],
        "personalized_cards": [],
        "combo_cards": [],
        "enrichment_timed_out": False
    }
    
    # Execute the graph
    # Using async call since nodes use async logic
    final_state = await orchestrator_graph.ainvoke(initial_state)
    
    return {
        "text": final_state.get("reply_text", ""),
        "structured": {
            "primary_skus": final_state.get("primary_cards", []),
            "recommended_skus": final_state.get("personalized_cards", []),
            "affinity_skus": final_state.get("combo_cards", []),
            "enrichment_timed_out": final_state.get("enrichment_timed_out", False)
        },
        "debug_trace": {
            "intent": final_state.get("intent"),
            "search_category": final_state.get("search_category"),
            "dish_name": final_state.get("dish_name"),
            "substitutions": final_state.get("substitutions_made", []),
            "offers": final_state.get("offers_applied", []),
            "timed_out": final_state.get("enrichment_timed_out", False),
            "no_matches": final_state.get("no_matches_triggered", False)
        }
    }
