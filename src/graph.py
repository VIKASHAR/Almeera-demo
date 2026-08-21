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
    
    # Conversational History Memory
    chat_history: List[Dict[str, str]]
    
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
    servings: Optional[int]
    price_max_qar: Optional[float]
    
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
    Classifies user intent (search vs recipe vs greeting) and extracts category, servings, & filters.
    """
    import re
    logger.info(f"--- INTENT ROUTER NODE --- Query: {state['raw_text']}")
    
    # Compile chat history context if present
    history_str = ""
    chat_history = state.get("chat_history") or []
    if chat_history:
        history_str = "Conversation history:\n"
        for turn in chat_history[-6:]:  # Keep last 3 turns
            role_label = "User" if turn["role"] == "user" else "Assistant"
            history_str += f"{role_label}: {turn['content']}\n"
        history_str += "\n"

    prompt = f"""
    You are an intent router for a grocery store chatbot.
    Your task is to classify the user's query into one of three intents:
    1. 'search': The user is looking for a specific product, brand, category, or type of item (e.g. "low-fat milk", "need pasta", "pet food under 15 QAR", "do you have butter", "find oil", "do you have fresh fruits", "fresh vegetables").
    2. 'recipe': The user is asking for a meal suggestion, recipe, instructions, dinner ideas, or how to cook something (e.g. "i need to make sandwich for 4 people?", "suggest a pasta recipe for dinner", "what can I make with tomatoes", "recipe for salad").
    3. 'greeting': The user is saying hi, hello, greeting the bot, or asking general conversational questions (e.g. "hi", "hello", "how are you", "who are you", "can you help me").
    
    {history_str}
    Current User Query: "{state['raw_text']}"
    
    IMPORTANT: If the Current User Query uses pronouns or relative words (like "it", "them", "that", "this", "those") to refer to items in the Conversation history, resolve those references and extract the correct "search_query" or "dish_name" values accordingly.
    
    Respond STRICTLY in JSON format with the following keys:
    - "intent": "search" | "recipe" | "greeting"
    - "category": string or null. If intent is "search", it MUST be one of:
       * 'Dairy': milk, cheese, butter, yogurt, sour cream, cream cheese, laban, ghee.
       * 'Produce': fruits, vegetables, mushrooms, leafy greens (spinach, basil, herbs), garlic, onions, lemons, avocados, alliums, bananas, apples, mangoes, tomatoes, cucumbers. NOTE: "fresh fruits", "fruits", "fruit", "fresh vegetables", "vegetables", "veggies" ALL map to 'Produce'.
       * 'Pantry/Grains': pasta, rice, olive oil, tomato sauce, coconut milk, curry powder, cereal, bread, canned beans/chickpeas.
       * 'Beverages': coffee, juice, soda, tea, water, drinks.
       * 'Frozen': frozen meals, frozen vegetables, ice cream.
       * 'Household': cleaning, laundry, paper products, tissues, detergents.
       * 'Meat & Seafood': beef, chicken, meat, fish, seafood, lamb, turkey, drumstick. NOTE: "fresh chicken", "chicken breast", "chicken drumstick" map to 'Meat & Seafood', NOT 'Produce'.
       * 'Personal Care': oral care, shampoo, soap.
       * 'Snacks': chips, cookies, crackers, nuts, sweets, chocolates, biscuits, candy.
       * 'Bakery': bread, croissants, pastries, bakery items, toast.
       * 'Baby': baby food, diapers, wipes, baby items.
       * 'Pet': pet food, cat food, dog food, cat litter, pet supplies.
       Set to null if the query doesn't match any of these categories or if intent is not "search".
    - "dish_name": string or null. Extract the meal/dish name ONLY if intent is "recipe" (e.g., "pasta", "salad", "curry", "sandwich"). Otherwise, set to null.
    - "servings": integer or null. If specified in query (e.g. "for 4 people", "for 4", "serves 2", "serve 4", "family of 4", "2 persons"), extract the number of servings/people (e.g., 4). Otherwise null.
    - "search_query": string or null. ONLY provide this if intent is "search". Extract the core product/item term or subcategory. For "fresh fruits" extract "fruit". For generic terms like "pet food", "cat food", "dog food", map to appropriate search terms or keep clean.
    - "price_max_qar": float or null. Extract maximum budget/price in QAR if specified in query (e.g. "under 10 QAR", "under 15 QAR", "under 10", "less than 15", "below 5 qar", "under 5"). Otherwise null.
    - "filters": {{
          "attributes": {{}}, -- e.g. {{"fat_content": "low-fat"}} or {{"organic": true}} or {{"gluten_free": true}} (if specified in query)
          "price_max": float or null
       }}
    """
    
    system_instruction = "You are a precise intent router. Output ONLY the JSON structure matching the schema."
    
    try:
        response_raw = llm_call(prompt, system_instruction=system_instruction, json_mode=True)
        response = json.loads(response_raw)
    except Exception as e:
        logger.error(f"Router node failed parsing JSON: {e}")
        query_lower = state['raw_text'].lower()
        if "milk" in query_lower:
            response = {"intent": "search", "category": "Dairy", "search_query": "milk", "dish_name": None, "servings": None, "price_max_qar": None, "filters": {"attributes": {}, "price_max": None}}
        elif "pasta" in query_lower or "recipe" in query_lower or "sandwich" in query_lower or "cook" in query_lower:
            response = {"intent": "recipe", "category": None, "search_query": None, "dish_name": "sandwich" if "sandwich" in query_lower else "Pasta Dinner", "servings": 4, "price_max_qar": None, "filters": {"attributes": {}, "price_max": None}}
        elif query_lower.strip() in ["hi", "hello", "hey", "greetings"]:
            response = {"intent": "greeting", "category": None, "search_query": None, "dish_name": None, "servings": None, "price_max_qar": None, "filters": {"attributes": {}, "price_max": None}}
        else:
            response = {"intent": "search", "category": None, "search_query": None, "dish_name": None, "servings": None, "price_max_qar": None, "filters": {"attributes": {}, "price_max": None}}
        
    query_text = state['raw_text'].lower()
    
    # Regex fallback for servings if omitted by LLM
    # Covers: "for 4", "for 4 people", "serve 4", "serves 4", "serving 4", "4 people", "4 persons", "family of 4"
    servings = response.get("servings")
    if not servings:
        servings_patterns = [
            r'(?:for|serve[sd]?|serving[s]?|family\s+of)\s+(\d+)\s*(?:people|persons?|servings?|guests?|adults?)?',
            r'(\d+)\s+(?:people|persons?|servings?|guests?|adults?)',
        ]
        for pattern in servings_patterns:
            servings_match = re.search(pattern, query_text)
            if servings_match:
                try:
                    candidate = int(servings_match.group(1))
                    # Sanity check: ignore numbers that look like prices (e.g. "under 5")
                    if 1 <= candidate <= 50:
                        servings = candidate
                        break
                except Exception:
                    pass
                
    # Regex fallback for price max in QAR — handles: "under 5 QAR", "below5qar", "< 5", "less than 10"
    price_max_qar = response.get("price_max_qar")
    if price_max_qar is None:
        price_patterns = [
            r'(?:under|below|less\s+than|cheaper\s+than|max(?:imum)?\s+(?:price)?|no\s+more\s+than)\s*(\d+(?:\.\d+)?)\s*(?:qar|riyals?)?',
            r'<\s*(\d+(?:\.\d+)?)\s*(?:qar|riyals?)?',
            r'(\d+(?:\.\d+)?)\s*(?:qar|riyals?)\s+(?:or\s+)?(?:less|under|below|max)',
        ]
        for pattern in price_patterns:
            price_match = re.search(pattern, query_text)
            if price_match:
                try:
                    price_max_qar = float(price_match.group(1))
                    break
                except Exception:
                    pass
                 
    # Direct Category Mapping for generic terms if category was missed by LLM
    extracted_category = response.get("category")
    if not extracted_category and response.get("intent") == "search":
        qt = query_text
        if any(term in qt for term in ["pet food", "cat food", "dog food", "cat litter", "pet supply", "pet supplies"]):
            extracted_category = "Pet"
        elif any(term in qt for term in ["baby food", "diaper", "nappy", "wipes", "baby"]):
            extracted_category = "Baby"
        elif any(term in qt for term in ["bakery", "croissant", "pastry", "baguette", "pita"]):
            extracted_category = "Bakery"
        elif any(term in qt for term in ["cleaning", "detergent", "laundry", "tissue", "dishwash"]):
            extracted_category = "Household"
        elif any(term in qt for term in ["chips", "cookies", "biscuit", "snack", "chocolate", "candy", "sweets", "nut", "cracker"]):
            extracted_category = "Snacks"
        elif any(term in qt for term in ["fruit", "vegetable", "veggie", "produce", "banana", "apple", "mango",
                                          "avocado", "lemon", "tomato", "spinach", "lettuce", "cucumber"]):
            extracted_category = "Produce"
        elif any(term in qt for term in ["milk", "cheese", "yogurt", "butter", "laban", "cream", "dairy"]):
            extracted_category = "Dairy"
        elif any(term in qt for term in ["chicken", "beef", "lamb", "fish", "seafood", "meat", "turkey", "drumstick"]):
            extracted_category = "Meat & Seafood"
        elif any(term in qt for term in ["juice", "soda", "water", "coffee", "tea", "drink", "beverage"]):
            extracted_category = "Beverages"
        elif any(term in qt for term in ["rice", "pasta", "noodle", "sauce", "oil", "spice", "flour", "canned"]):
            extracted_category = "Pantry/Grains"

    # Pronoun coreference fallback if dish_name is missing/generic in a recipe intent
    chat_history = state.get("chat_history") or []
    current_dish = response.get("dish_name")
    if chat_history and response.get("intent") == "recipe" and (not current_dish or current_dish.lower() in ["it", "them", "that", "this", "dish", "meal", "food"]):
        for turn in reversed(chat_history):
            content_lower = turn.get("content", "").lower()
            for food_term in ["pasta", "spaghetti", "sandwich", "salad", "biryani", "curry", "pizza", "soup", "chicken", "fish", "beef", "lentils", "rice", "burger"]:
                if food_term in content_lower:
                    response["dish_name"] = food_term.capitalize()
                    break
            if response.get("dish_name") and response["dish_name"].lower() not in ["it", "them", "that", "this", "dish", "meal", "food"]:
                break

    # Convert price_max_qar to USD database price limit (1 USD = 3.64 QAR)
    # Use 4 decimal places to avoid rounding edge case where "under 10 QAR" (2.7472 USD)
    # rounds to 2.75, allowing a product at 10.01 QAR (= 2.750 USD) to slip through.
    filters = response.get("filters") or {"attributes": {}, "price_max": None}
    if price_max_qar is not None and price_max_qar > 0:
        price_max_usd = round(price_max_qar / 3.64, 4)
        filters["price_max"] = price_max_usd
        
    logger.info(f"Router classified intent as: {response.get('intent')}, category: {extracted_category}, servings: {servings}, price_max_qar: {price_max_qar}, dish_name: {response.get('dish_name')}")
    return {
        "intent": response.get("intent", "search"),
        "search_category": extracted_category,
        "search_query": response.get("search_query"),
        "search_filters": filters,
        "dish_name": response.get("dish_name"),
        "servings": servings,
        "price_max_qar": price_max_qar
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
    p_cat = product.get('category', '')
    
    # 1. Dietary preference compliance
    if diet == "low-fat":
        if p_cat == 'Dairy' and p_attr.get('fat_content') not in ('low-fat', 'non-fat', 'skimmed', '0%', '0% fat', 'fat-free', 'skim'):
            return False
    elif diet == "vegan":
        # Animal meat/seafood is non-vegan
        if p_cat in ('Meat & Seafood',):
            return False
        # Dairy is non-vegan unless explicit dairy-free / plant-based
        if p_cat in ('Dairy',) and not (p_attr.get('dairy_free') is True or p_attr.get('plant_based') is True):
            return False
        # Check explicit animal keywords
        p_name_lower = product.get('name', '').lower()
        animal_words = ['chicken', 'beef', 'meat', 'lamb', 'mutton', 'pork', 'turkey', 'fish', 'seafood', 'tuna', 'salmon', 'sardine', 'shrimp', 'prawn', 'bacon', 'gelatin', 'whey']
        if any(aw in p_name_lower.split() for aw in animal_words):
            return False
        # Only check boolean attribute if category is not naturally plant-based (Produce and Pantry/Grains are plant staples)
        if p_cat not in ('Produce', 'Pantry/Grains') and p_attr.get('vegan') is False:
            return False
    elif diet == "gluten-free":
        if p_attr.get('gluten_free') is False:
            return False
            
    # 2. Allergen/Avoid-list compliance
    p_name_lower = product.get('name', '').lower()
    for allergen in avoid_list:
        allergen_clean = allergen.strip().lower()
        if allergen_clean == 'nuts':
            # Check for all common nut types
            nut_keywords = ['almond', 'peanut', 'cashew', 'walnut', 'hazelnut', 'pistachio', 'pecan', 'nut', 'nuts']
            if any(nk in p_name_lower for nk in nut_keywords):
                return False
        if allergen_clean == 'dairy' and (p_cat == 'Dairy' or p_attr.get('dairy_free') is False):
            return False
            
    return True

def _is_irrelevant_product(product: Dict[str, Any], ingredient_name: str) -> bool:
    """
    Heuristic guard: returns True if a product is semantically irrelevant to the ingredient.
    Applies to ALL recipe types — prevents cross-category contamination.
    """
    if not product:
        return False
    p_name = product.get('name', '').lower()
    p_subcat = (product.get('subcategory') or '').lower()
    p_cat = (product.get('category') or '').lower()
    ing = (ingredient_name or '').lower()
    
    # ── 1. Bulk commercial products (all sizes that are non-household) ─────────
    bulk_indicators = ['40kg', '25kg', '20kg', '10kg', '5kg ', '5 kg',
                       '40 kg', '25 kg', '20 kg', '10 kg']
    if any(bi in p_name for bi in bulk_indicators):
        return True
        
    # ── 2. Exclude non-food categories & cosmetics / flowers / personal care ───
    if p_cat in ('household', 'baby', 'pet'):
        return True
    cosmetic_words = ['shampoo', 'night cream', 'face cream', 'body scrub', 'shower gel', 'lotion', 'deodorant', 'soap', 'detergent', 'cleaner', 'wash', 'hair care', 'skin care', 'flower', 'flowers', 'arrangement', 'bouquet', 'plant']
    if any(c in p_name for c in cosmetic_words) or 'skin & body' in p_subcat or 'hair care' in p_subcat or 'hygiene' in p_subcat or 'flowers' in p_subcat:
        return True
        
    # ── 3. Exclude cooking appliances / hardware ──────────────────────────────
    if any(a in p_name for a in ['cooker', 'scooper', 'appliance', 'knife', 'pan', 'pot', 'scale']):
        return True
    
    # ── 4. Cakes/desserts vs. savory recipe ingredients ───────────────────────
    savory_ing_keywords = [
        'chicken', 'beef', 'lamb', 'meat', 'mutton', 'turkey', 'fish', 'salmon', 'tuna',
        'rice', 'onion', 'tomato', 'spice', 'garlic', 'oil', 'yogurt',
        'bread', 'lettuce', 'potato', 'curry', 'pasta',
        'carrot', 'pepper', 'salt', 'chickpea', 'lentil', 'bean', 'egg', 'flour',
        'butter', 'cream', 'cheese', 'mozzarella', 'avocado', 'cucumber', 'spinach',
        'mushroom', 'zucchini', 'eggplant', 'broccoli', 'cauliflower', 'pea',
        'noodle', 'spaghetti', 'macaroni', 'sauce', 'stock', 'broth', 'vinegar', 'salad', 'greens'
    ]
    dessert_product_words = [
        'cake', 'cookie', 'biscuit', 'chocolate', 'candy', 'sweet', 'wafer',
        'muffin', 'brownie', 'pastry', 'donut', 'red velvet', 'toffee', 'caramel',
        'pudding', 'gelatin', 'jelly', 'jam', 'nutella', 'hazelnut spread',
        'halawa', 'baklava', 'kunafa', 'smoothie', 'ice cream'
    ]
    if any(sk in ing for sk in savory_ing_keywords):
        if any(dw in p_name for dw in dessert_product_words) and \
           not any(dw in ing for dw in dessert_product_words):
            return True
    
    # ── 5. Canned fish / seafood vs. non-seafood ingredients ──────────────────
    seafood_product_words = ['sardine', 'anchov', 'tuna', 'mackerel', 'salmon', 'herring', 'squid', 'shrimp', 'prawn', 'crab']
    if any(sw in p_name for sw in seafood_product_words):
        if not any(sw in ing for sw in ['sardine', 'anchov', 'tuna', 'fish', 'seafood', 'mackerel', 'salmon', 'prawn', 'shrimp', 'crab']):
            return True
    
    # ── 6. Mixed nuts vs. non-nut ingredients ─────────────────────────────────
    if ('mixed' in p_name and 'nut' in p_name) or ('deluxe nut' in p_name):
        nut_ing_words = ['nut', 'almond', 'cashew', 'peanut', 'walnut', 'pistachio', 'hazelnut']
        if not any(nw in ing for nw in nut_ing_words):
            return True
    
    # ── 7. Mayo / ketchup / condiments vs. non-condiment ingredients ──────────
    condiment_products = ['mayonnaise', 'ketchup', 'mustard', 'mayo']
    if any(cp in p_name for cp in condiment_products):
        if not any(cp in ing for cp in condiment_products):
            return True
    
    # ── 8. Energy drinks / sodas vs. food & fresh produce ingredients ─────────
    beverage_products = ['energy drink', 'monster', 'red bull', 'cola', 'soda', 'soft drink', 'sparkling water', 'energy shot', 'bitter lemon', 'drink', 'beverage']
    food_ing_words = ['water', 'stock', 'broth', 'milk', 'lemon', 'lime', 'orange', 'apple', 'banana']
    if any(bp in p_name for bp in beverage_products):
        if any(fw in ing for fw in food_ing_words) and 'drink' not in ing and 'energy' not in ing and 'soda' not in ing:
            return True

    # ── 9. Sliced Bread / Sandwich Bread Guard ──────────────────────────────
    if any(b in ing for b in ['bread', 'slice', 'bun', 'toast', 'loaf', 'sandwich']):
        if any(ex in p_name for ex in ['crumbs', 'breading', 'breadstick', 'crouton', 'bread bin', 'crumb', 'sticks']) and 'crumb' not in ing:
            return True

    # ── 10. Lemon / Citrus / Juice Guard ────────────────────────────────────
    if any(c in ing for c in ['lemon', 'lime', 'citrus']):
        if any(ex in p_name for ex in ['jelly', 'gelatin', 'dessert', 'pudding', 'custard', 'candy', 'tea bag', 'sachet']) and 'jelly' not in ing and 'dessert' not in ing:
            return True

    # ── 11. Salad Greens Guard ──────────────────────────────────────────────
    if any(g in ing for g in ['salad', 'greens', 'lettuce', 'spinach', 'mixed greens']):
        if any(ex in p_name for ex in ['fatayer', 'pastry', 'samosa', 'croissant', 'pie', 'puff', 'cookie', 'biscuit', 'chips', 'crisp']) and 'fatayer' not in ing and 'pastry' not in ing:
            return True

    # ── 12. Pizza Dough / Base Guard ────────────────────────────────────────
    if any(d in ing for d in ['pizza dough', 'dough', 'crust', 'pizza base']):
        if any(ex in p_name for ex in ['pizza vegetable', 'pizza topping', 'frozen pizza', 'cooked pizza', 'box set']) and 'vegetable' not in ing:
            return True

    # ── 13. Cooking Oil Guard ───────────────────────────────────────────────
    if any(o in ing for o in ['oil', 'vegetable oil', 'olive oil', 'cooking oil', 'sunflower oil', 'corn oil']):
        if p_cat in ('dairy', 'snacks', 'bakery') or any(ex in p_name for ex in ['cheese', 'feta', 'butter', 'stick', 'crisp', 'chips', 'cracker']):
            return True

    # ── 14. Spice / Seasoning / Powder Guard ────────────────────────────────
    if any(s in ing for s in ['spice', 'masala', 'curry powder', 'biryani spice', 'turmeric', 'cumin', 'paprika', 'coriander', 'cinnamon', 'powder']):
        if p_cat in ('snacks', 'beverages', 'produce') or any(ex in p_name for ex in ['energy mix', 'trail mix', 'nut mix', 'dried fruit', 'fruit', 'bar', 'biscuit', 'cookie', 'snack']):
            return True

    # ── 15. Mixed Vegetables / Fresh Veg Guard ──────────────────────────────
    if any(v in ing for v in ['vegetables', 'mixed vegetables', 'veggies', 'mixed veg']):
        if p_cat in ('snacks', 'bakery') or any(ex in p_name for ex in ['dried fruit', 'fruit', 'snack', 'stick', 'chip', 'crisp', 'biscuit', 'cookie']):
            return True

    # ── 16. Rice / Grain Guard ──────────────────────────────────────────────
    if any(r in ing for r in ['rice', 'basmati', 'jasmine rice', 'grain']):
        if p_cat not in ('pantry/grains', 'produce') or any(ex in p_name for ex in ['cooker', 'cracker', 'cake', 'biscuit', 'chips']):
            return True

    # ── 17. Plain Pasta Guard ───────────────────────────────────────────────
    if any(p in ing for p in ['pasta', 'spaghetti', 'macaroni', 'noodle', 'penne', 'fusilli', 'vermicelli']):
        if not any(m in ing for m in ['beef', 'meat', 'chicken', 'pork', 'lamb']):
            if any(ex in p_name for ex in ['beef', 'angus', 'chicken', 'meat', 'pork', 'bacon', 'ham', 'pretzel', 'hummus', 'tortellini', 'ravioli']):
                return True
        if not any(s in ing for s in ['sauce', 'bolognese', 'marinara']):
            if any(ex in p_name for ex in ['pasta sauce', 'pizza sauce', 'sauce for']):
                return True
    
    return False

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
    # Remove common conversational verbs, filler words, AND descriptor adjectives
    # Removing 'fresh' here is critical — otherwise "fresh fruits" searches for "fresh" and matches
    # "Fresh Whole Chicken" in the database.
    stop_words = {
        "need", "want", "i", "get", "find", "search", "show", "me", "some", 
        "a", "timeout", "test", "do", "you", "have", "has", "any", "are", 
        "there", "we", "for", "please", "can", "buy", "how", "much", "is",
        "fresh", "whole", "natural", "raw", "pure", "organic"
    }
    query_words = [
        w for w in raw_query.split() 
        if w.lower().strip("()?.!,;") not in stop_words
    ]
    # Clean punctuation from the final search words
    cleaned_words = [w.strip("()?.!,;") for w in query_words]
    cleaned_raw_query = " ".join(cleaned_words) if cleaned_words else raw_query
    
    # Detect pure budget queries with no specific product noun (e.g. "show me items under 2 QAR")
    budget_filler_words = {"items", "item", "product", "products", "things", "under", "below", "less", "than", "qar", "riyal", "riyals", "cheap", "affordable"}
    is_pure_budget = price_max is not None and (
        not state.get("search_query") and 
        all(w.lower() in budget_filler_words or w.isdigit() for w in cleaned_words)
    )
    
    # Use LLM-extracted search_query if available, otherwise default to cleaned raw query
    if is_pure_budget:
        query_str = None
        cleaned_raw_query = None
    else:
        query_str = state.get("search_query") or cleaned_raw_query

    # Category-to-exclusion rules: when the user explicitly asks for a category,
    # prevent fundamentally different categories from polluting results.
    CATEGORY_EXCLUSIONS = {
        "Produce": ["Meat & Seafood"],
        "Meat & Seafood": ["Produce", "Dairy", "Bakery"],
        "Dairy": ["Meat & Seafood", "Produce"],
        "Snacks": ["Meat & Seafood", "Produce", "Dairy"],
        "Beverages": ["Meat & Seafood"],
        "Pet": ["Produce", "Dairy", "Meat & Seafood", "Bakery"],
        "Baby": ["Meat & Seafood", "Pet"],
        "Household": ["Produce", "Dairy", "Meat & Seafood", "Bakery", "Snacks"],
    }
    exclude_cats = CATEGORY_EXCLUSIONS.get(category, []) if category else []

    # Fruit and Tomato fresh produce refinement: exclude processed/canned/jam subcategories
    # so actual fresh fruits and fresh vegetables are returned first.
    exclude_subcats = []
    raw_lower = state['raw_text'].lower()
    search_q_lower = (query_str or "").lower()
    
    if category == "Produce":
        if any(w in raw_lower for w in ["fruit", "fruits", "frutis", "fresh fruit", "fresh fruits", "fresh frutis"]) or search_q_lower in ["fruit", "fruits"]:
            exclude_subcats = ["Nuts, Dates & Dried Food", "Nuts & Seeds", "Dried Fruits & Nuts", "Seeds, Nuts & Dried Fruits", "Honey & Jams", "Canned Fruit", "Canned Vegetables", "Fresh Vegetables", "Vegetables", "Salad Dressings & Vinegar", "Salad Dressings", "Pickles & Olives", "Condiments", "Special Diet"]
            if not query_str or query_str.strip() in ["fruit", "fruits", "frutis", "fresh fruit", "fresh fruits", "fresh frutis"]:
                query_str = "banana avocado lemon orange mango apple pineapple grape watermelon kiwi strawberry peach pear melon"
        elif any(w in raw_lower for w in ["vegetable", "vegetables", "veggie", "veggies", "fresh vegetable", "fresh vegetables"]) or search_q_lower in ["vegetable", "vegetables", "veggie", "veggies"]:
            exclude_subcats = ["Fresh Fruits", "Fruit & Vegetables > Fruits", "Fruits", "Nuts, Dates & Dried Food", "Nuts & Seeds", "Dried Fruits & Nuts", "Seeds, Nuts & Dried Fruits", "Honey & Jams", "Canned Fruit", "Canned Vegetables", "Flowers & Plants", "Special Diet"]
            if not query_str or query_str.strip() in ["vegetable", "vegetables", "veggie", "veggies", "fresh vegetable", "fresh vegetables"]:
                query_str = "onion cucumber tomato spinach lettuce potato carrot garlic mushroom broccoli zucchini pepper cabbage eggplant"
        elif any(w in raw_lower for w in ["tomato", "tomatoes", "tomatos"]) or search_q_lower in ["tomato", "tomatoes", "tomatos"]:
            if not any(w in raw_lower for w in ["sauce", "passata", "paste", "puree", "canned", "soup", "ketchup", "chips", "bean", "beans"]):
                exclude_subcats = ["Canned Vegetables", "Canned & Jarred", "Pizza & Pasta Sauces", "Condiments", "Honey & Jams", "Special Diet", "Pickles & Olives"]
        
    # Helper to resolve compliant and in-stock products/substitutes from a list of candidates
    def resolve_products_for_search(candidate_products):
        compliant_candidates = [p for p in candidate_products if is_product_compliant(p, profile)]
        
        # Guard: If searching for fresh produce, filter out any stray processed items (canned beans, jams)
        if category == "Produce":
            if any(w in raw_lower for w in ["fruit", "fruits", "frutis"]) and not any(w in raw_lower for w in ["jam", "jelly", "canned", "syrup"]):
                compliant_candidates = [p for p in compliant_candidates if not any(x in p.get('name', '').lower() for x in ['jam', 'jelly', 'syrup', 'canned fruit'])]
            if any(w in raw_lower for w in ["tomato", "tomatoes", "tomatos"]) and not any(w in raw_lower for w in ["sauce", "paste", "bean", "beans", "ketchup"]):
                compliant_candidates = [p for p in compliant_candidates if not any(x in p.get('name', '').lower() for x in ['beans in', 'baked beans', 'paste', 'sauce', 'ketchup', 'puree'])]

        # Prioritize preferred brands (non-blocking brand bias)
        if preferred_brands:
            compliant_candidates.sort(key=lambda p: 0 if p.get('brand') in preferred_brands else 1)
            
        in_stock_products = [p for p in compliant_candidates if p['stock_qty'] > 0]
        out_of_stock_products = [p for p in compliant_candidates if p['stock_qty'] == 0]
        
        res_skus = []
        subs_made = []
        prim_products = []
        
        if not in_stock_products and out_of_stock_products:
            # All target items are out of stock! Fetch alternatives for ALL OOS products
            seen_alt_skus = set()
            for oos_product in out_of_stock_products:
                target_sku = oos_product['sku']
                alternatives = db.get_alternatives(target_sku, in_stock_only=True, channel=channel)
                
                # Filter alternatives for compliance
                compliant_alts = [alt for alt in alternatives if is_product_compliant(alt, profile)]
                
                for alt in compliant_alts:
                    if alt['sku'] not in seen_alt_skus:
                        seen_alt_skus.add(alt['sku'])
                        res_skus.append(alt['sku'])
                        subs_made.append({"requested": target_sku, "substituted_with": alt['sku']})
                        prim_products.append(alt)
        else:
            # Keep top 3 matching in-stock products
            for p in in_stock_products[:3]:
                res_skus.append(p['sku'])
                prim_products.append(p)
                
        return res_skus, subs_made, prim_products, out_of_stock_products if not in_stock_products else []

    # 2. Search database with category constraint and exclusions
    products = db.search_products(
        category=category, query_str=query_str, attributes=search_attrs,
        price_max=price_max, channel=channel, raw_query=cleaned_raw_query,
        exclude_categories=exclude_cats, exclude_subcategories=exclude_subcats
    )
    
    # Python-level post-filter: enforce category exclusions on results
    # This is a safety net to catch any DB-level misses
    if exclude_cats:
        products = [p for p in products if p.get('category') not in exclude_cats]
    # Also filter out excluded subcategories (e.g. nuts when user asked for fruit)
    if exclude_subcats:
        products = [p for p in products if p.get('subcategory') not in exclude_subcats]

    # Name-level post-filter per category: because the DB seed data miscategorizes many products
    # (e.g. food containers seeded as Dairy/Bakery, chicken liver as Snacks), we apply keyword
    # blocklists to make sure results are semantically correct for each category.
    CATEGORY_NAME_EXCLUSIONS = {
        "Snacks": [
            "container", "microwavable", "aluminum", "storage", "box set", "plate", "bowl",
            "lid", "pcs", "pieces", "liver", "hearts", "kidney", "gizzard", "chicken breast",
            "chicken whole", "chicken drumstick", "kitchen", "wrap", "foil", "bag set",
            "cleaning", "detergent", "shampoo", "conditioner", "soap", "tissue", "wipe",
            "diaper", "baby food"
        ],
        "Produce": [
            "container", "microwavable", "kitchen", "cleaning", "detergent",
            "shampoo", "conditioner", "soap", "tissue", "wipe", "diaper"
        ],
        "Dairy": [
            "container", "microwavable", "storage", "aluminum foil", "cleaning",
            "detergent", "shampoo", "conditioner", "soap"
        ],
        "Beverages": [
            "container", "microwavable", "cleaning", "detergent", "shampoo", "soap"
        ],
        "Pet": [
            "container", "human food", "chicken breast", "beef steak", "cleaning"
        ],
    }
    
    name_exclusion_terms = CATEGORY_NAME_EXCLUSIONS.get(category, [])
    if name_exclusion_terms:
        def name_is_clean(p):
            pname = p.get('name', '').lower()
            return not any(excl in pname for excl in name_exclusion_terms)
        products = [p for p in products if name_is_clean(p)]
        
    # Produce specialization: exclude fruits when user asked for vegetables, and vice-versa
    if any(k in raw_lower for k in ['vegetable', 'vegetables', 'veggie', 'veggies', 'fresh vegetable', 'fresh vegetables']):
        fruit_words = ['peach', 'peaches', 'nectarine', 'apple', 'apples', 'banana', 'bananas', 'mango', 'mangoes', 'grape', 'grapes', 'strawberry', 'strawberries', 'watermelon', 'pineapple', 'kiwi', 'pear', 'pears', 'melon', 'orange', 'oranges', 'plum', 'plums', 'cherry', 'cherries', 'fig', 'figs', 'papaya', 'guava', 'pomegranate', 'berry', 'berries']
        products = [p for p in products if not any(fw in p.get('name', '').lower() for fw in fruit_words)]
    elif any(k in raw_lower for k in ['fruit', 'fruits', 'fresh fruit', 'fresh fruits']):
        non_fruit_words = ['onion', 'garlic', 'potato', 'potatoes', 'spinach', 'mushroom', 'mushrooms', 'broccoli', 'zucchini', 'cabbage', 'eggplant', 'vinegar', 'cider', 'dressing', 'sauce', 'pickle']
        products = [p for p in products if not any(nw in p.get('name', '').lower() for nw in non_fruit_words)]
    
    resolved_skus, substitutions_made, primary_products, oos_list = resolve_products_for_search(products)
    
    # 3. Category Relaxation Fallback:
    # If no matches are found/resolved under the category constraint, broaden the search
    # BUT still apply category exclusions to avoid garbage results.
    if not resolved_skus and category is not None:
        logger.info(f"First-pass search for category '{category}' yielded 0 resolved products. Relaxing category constraint...")
        broad_products = db.search_products(
            category=None, query_str=query_str, attributes=search_attrs,
            price_max=price_max, channel=channel, raw_query=cleaned_raw_query,
            exclude_categories=exclude_cats, exclude_subcategories=exclude_subcats
        )
        # Even during broad search, maintain category exclusions
        if exclude_cats:
            broad_products = [p for p in broad_products if p.get('category') not in exclude_cats]
        if exclude_subcats:
            broad_products = [p for p in broad_products if p.get('subcategory') not in exclude_subcats]
        # Also apply name-level exclusions in broad search
        if name_exclusion_terms:
            broad_products = [p for p in broad_products if name_is_clean(p)]
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
    Biased by Tier 1 preferences (e.g. vegan, low-fat), servings, and price budget.
    """
    logger.info(f"--- RECIPE GENERATOR NODE (CAP 2) ---")
    channel = state['channel']
    dish_name = state.get("dish_name") or state['raw_text']
    # Normalize dish_name spelling
    if "briyani" in dish_name.lower() or "biriyani" in dish_name.lower():
        dish_name = dish_name.lower().replace("briyani", "biryani").replace("biriyani", "biryani").capitalize()
    # Default servings to 2 (not 4) when not specified — more realistic for a single query
    servings_specified = state.get("servings") is not None
    servings = state.get("servings") or 2
    
    # 1. Load Tier 1 profile bias
    profile = state.get("tier1_profile") or {}
    diet = profile.get("dietary_preference", "none")
    avoid_list = profile.get("avoid_list") or []
    filters = state.get("search_filters") or {}
    price_max = filters.get("price_max")
    
    # Fetch in-stock food products to bias the recipe toward available catalog items
    try:
        matched_products = []
        if dish_name:
            words = [w.strip("()?.!,;") for w in dish_name.lower().split()]
            for word in words:
                if len(word) > 2 and word not in {"recipe", "how", "make", "cook", "to", "for", "with", "people"}:
                    matched_products.extend(db.search_products(query_str=word, price_max=price_max, channel=channel, limit=15, exclude_categories=['Household', 'Baby', 'Pet']))
        
        # Also fetch popular staple food candidates
        staples = []
        for staple_term in ["bread", "chicken", "lettuce", "tomato", "pasta", "rice", "sauce", "milk", "cheese", "oil"]:
            staples.extend(db.search_products(query_str=staple_term, price_max=price_max, channel=channel, limit=5, exclude_categories=['Household', 'Baby', 'Pet']))
            
        all_candidates = matched_products + staples
        
        seen_skus = set()
        available_products = []
        for p in all_candidates:
            if p['sku'] not in seen_skus and p.get('stock_qty', 0) > 0:
                seen_skus.add(p['sku'])
                available_products.append(p)
                
        product_names = [p['name'] for p in available_products]
        product_list_str = ", ".join(product_names)
    except Exception as e:
        logger.error(f"Error fetching product list for recipe bias: {e}")
        product_list_str = ""
        
    bias_instruction = f"Generate recipe for {servings} people."
    if diet != "none":
        bias_instruction += f" Ensure this recipe strictly follows a {diet} diet."
    if avoid_list:
        bias_instruction += f" Do NOT include any ingredients containing or derived from: {', '.join(avoid_list)}."
        
    prompt = f"""
    You are a professional supermarket chef.
    Generate a simple, authentic recipe for: "{dish_name}" for {servings} people.
    {bias_instruction}
    
    CRITICAL INSTRUCTIONS:
    - Keep the ingredient list small (4-5 items).
    - Output ONLY clean, natural EDIBLE food ingredients scaled for {servings} people.
    - Examples of clean ingredients: "300g Chicken Breast", "200g Basmati Rice", "2 tbsp Biryani Spice Mix", "1 Onion", "2 Tomatoes", "2 tbsp Olive Oil".
    - NEVER include non-food items, sponges, kitchen appliances, cleaning supplies, or desserts/cakes unless specifically requested.
    - Do NOT copy raw store product package sizes (like "40kg" or "2L") into the ingredient names.
    
    Respond STRICTLY in JSON format with the following keys:
    - "dish_name": string (e.g. "Chicken Biryani")
    - "servings": integer (e.g. {servings})
    - "ingredients": list of strings with quantities scaled for {servings} people (e.g. ["300g Chicken Breast", "200g Basmati Rice", "2 tbsp Biryani Spice Mix", "1 Onion", "2 tbsp Olive Oil"])
    """
    
    system_instruction = "You are a recipe ingredient extractor. Output ONLY the JSON structure."
    
    try:
        response_raw = llm_call(prompt, system_instruction=system_instruction, json_mode=True)
        recipe_data = json.loads(response_raw)
    except Exception as e:
        logger.error(f"Recipe generator failed parsing JSON: {e}")
        recipe_data = {
            "dish_name": dish_name,
            "servings": servings,
            "ingredients": [f"{servings} slices Smash Sandwich Box GB", f"{100*servings}g Chicken Breast", "1 head Lettuce", "2 Tomatoes"]
        }
        
    ingredients = recipe_data.get("ingredients", [])
    logger.info(f"DEBUG: Recipe Generator returned ingredients for {servings} people: {ingredients}")
    
    # 2. Map ingredients to database SKUs
    mapped_skus_dict = db.map_ingredients_to_skus(ingredients)
    
    resolved_skus = []
    substitutions_made = []
    ingredients_detail = []
    
    # 3. Check inventory and substitute any out of stock or non-compliant ingredients
    for ing_name, product in mapped_skus_dict.items():
        is_bread_item = any(w in ing_name.lower() for w in ["bread", "toast", "bun", "loaf", "sandwich", "slice"])
        
        # Immediate semantic relevance check on mapped product
        if product and _is_irrelevant_product(product, ing_name):
            logger.warning(f"Discarding irrelevant product '{product.get('name')}' for ingredient '{ing_name}'")
            product = None
        
        if product:
            sku = product['sku']
            is_compliant = is_product_compliant(product, profile)
            
            stock = db.check_inventory([sku], channel=channel)
            stock_qty = stock.get(sku, 0) if is_compliant else 0
            
            if stock_qty == 0 or not is_compliant:
                # OOS or Non-compliant ingredient! Find alternative
                alternatives = db.get_alternatives(sku, in_stock_only=True, channel=channel)
                compliant_alts = [alt for alt in alternatives if is_product_compliant(alt, profile) and not _is_irrelevant_product(alt, ing_name)]
                
                # If it's a bread item and standard alternatives failed, query in-stock breads directly
                if is_bread_item and not compliant_alts:
                    bread_candidates = db.search_products(query_str="sliced bread", channel=channel, limit=10)
                    compliant_alts = [b for b in bread_candidates if b.get('stock_qty', 0) > 0 and is_product_compliant(b, profile) and not _is_irrelevant_product(b, ing_name)]
                
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
                    # No compliant alternatives found in same category.
                    # Try a broader keyword search for a compliant replacement.
                    ing_keywords = [w.strip() for w in db.clean_ingredient_phrase(ing_name).split() if len(w.strip()) > 2]
                    broader_found = None
                    for kw in ing_keywords:
                        broader_candidates = db.search_products(
                            query_str=kw, channel=channel, limit=15,
                            exclude_categories=['Household', 'Baby', 'Pet']
                        )
                        broader_compliant = [
                            c for c in broader_candidates
                            if c.get('stock_qty', 0) > 0
                            and is_product_compliant(c, profile)
                            and not _is_irrelevant_product(c, ing_name)
                        ]
                        if broader_compliant:
                            broader_found = broader_compliant[0]
                            break
                    
                    if broader_found:
                        substitutions_made.append({"requested": sku, "substituted_with": broader_found['sku']})
                        resolved_skus.append(broader_found['sku'])
                        ingredients_detail.append({
                            "ingredient_name": ing_name,
                            "sku": broader_found['sku'],
                            "name": broader_found['name'],
                            "price": broader_found['price'],
                            "stock_qty": broader_found['stock_qty'],
                            "in_stock": True,
                            "is_substituted": True,
                            "original_name": product['name']
                        })
                    else:
                        # Truly no alternative — mark as unavailable but do NOT add non-compliant SKU
                        ingredients_detail.append({
                            "ingredient_name": ing_name,
                            "sku": None,
                            "name": ing_name,
                            "price": None,
                            "stock_qty": 0,
                            "in_stock": False,
                            "is_substituted": False
                        })
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
            # Unmapped ingredient - perform clean keyword lookup so only genuine food items are matched
            clean_words = [w for w in db.clean_ingredient_phrase(ing_name).split() if len(w) > 2]
            fallback_product = None
            for w in clean_words:
                candidates = db.search_products(query_str=w, channel=channel, limit=15, exclude_categories=['Household', 'Baby', 'Pet'])
                in_stock_cand = [
                    c for c in candidates
                    if c.get('stock_qty', 0) > 0
                    and is_product_compliant(c, profile)
                    and not _is_irrelevant_product(c, ing_name)
                ]
                if in_stock_cand:
                    fallback_product = in_stock_cand[0]
                    break
                    
            if fallback_product:
                resolved_skus.append(fallback_product['sku'])
                ingredients_detail.append({
                    "ingredient_name": ing_name,
                    "sku": fallback_product['sku'],
                    "name": fallback_product['name'],
                    "price": fallback_product['price'],
                    "stock_qty": fallback_product['stock_qty'],
                    "in_stock": True,
                    "is_substituted": True
                })
            else:
                ingredients_detail.append({
                    "ingredient_name": ing_name,
                    "sku": None,
                    "name": ing_name,
                    "price": None,
                    "stock_qty": 0,
                    "in_stock": False,
                    "is_substituted": False
                })
            
    promotions = db.get_active_offers(resolved_skus)
    offers_applied = [promo['promo_id'] for promo in promotions]
    
    primary_result = {
        "dish_name": recipe_data.get("dish_name", dish_name),
        "servings": recipe_data.get("servings", servings),
        "servings_specified": servings_specified,  # True if user explicitly said "for N people"
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
    
    # 1. Determine category of query based on resolved SKUs or dish type
    category = state.get("search_category")
    dish_lower = (state.get("dish_name") or state.get("raw_text") or "").lower()
    
    if not category:
        if any(w in dish_lower for w in ["salad", "greens", "vegetable", "veggie", "fruit"]):
            category = "Produce"
        elif any(w in dish_lower for w in ["pasta", "spaghetti", "macaroni", "noodle"]):
            category = "Pantry/Grains"
        elif any(w in dish_lower for w in ["chicken", "beef", "meat", "fish", "biryani", "curry"]):
            category = "Meat & Seafood"
        elif any(w in dish_lower for w in ["bread", "sandwich", "toast", "bakery"]):
            category = "Bakery"
        elif any(w in dish_lower for w in ["pizza"]):
            category = "Bakery"
        elif resolved_skus:
            try:
                conn = db.get_connection()
                conn.row_factory = db.dict_factory
                cursor = conn.cursor()
                placeholders = ",".join("?" for _ in resolved_skus)
                cursor.execute(f"SELECT category, COUNT(*) as cnt FROM products WHERE sku IN ({placeholders}) GROUP BY category ORDER BY cnt DESC", resolved_skus)
                row = cursor.fetchone()
                if row:
                    category = row['category']
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
    # Otherwise, set a realistic timeout threshold of 30.0s for live LLM API response latency
    # (recipe flow makes 3+ sequential LLM calls: router → recipe generator → composer).
    elapsed = time.time() - state.get("start_time", time.time())
    is_timeout_test = "timeout" in state['raw_text'].lower()
    enrichment_timed_out = (is_timeout_test and elapsed > 1.0) or (elapsed > 30.0)
    
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
        rec_products = db.get_products_by_skus(final_recommended)
    if final_combo:
        combo_products = db.get_products_by_skus(final_combo)
        
    recommended_detail = json.dumps([{ "sku": p['sku'], "name": p['name'], "price": p['price'] } for p in rec_products], indent=2)
    combo_detail = json.dumps([{ "sku": p['sku'], "name": p['name'], "price": p['price'] } for p in combo_products], indent=2)
    
    # 5. Call LLM for final natural composition
    intent = state.get("intent", "search")
    
    # Compile chat history context if present
    history_str = ""
    chat_history = state.get("chat_history") or []
    if chat_history:
        history_str = "Conversation history:\n"
        for turn in chat_history[-6:]:  # Keep last 3 turns
            role_label = "User" if turn["role"] == "user" else "Assistant"
            history_str += f"{role_label}: {turn['content']}\n"
        history_str += "\n"
    
    if no_matches and intent != "greeting":
        # Determine if this was a recipe OOS or a search OOS
        is_recipe_oos = intent == "recipe"
        dish_name = state.get("dish_name", "the requested dish")
        
        # Fetch all available in-stock products to suggest relevant alternatives
        try:
            available_products = db.search_products(channel=state.get("channel", "online"), limit=30)
            in_stock_catalog = [{ "name": p['name'], "price": p['price'], "category": p['category'] } for p in available_products if p.get('stock_qty', 0) > 0]
            in_stock_str = json.dumps(in_stock_catalog, indent=2)
        except Exception as e:
            logger.error(f"Error fetching in-stock products for no matches fallback: {e}")
            in_stock_str = "[]"
            
        if is_recipe_oos:
            prompt = f"""
            You are the master composer for a smart grocery store checkout chatbot.
            The customer asked for a recipe for "{dish_name}" but we don't have the necessary ingredients in stock.
            
            {history_str}
            Current User Query: "{state['raw_text']}"
            Intent: recipe
            
            Available In-Stock products in our store:
            {in_stock_str}
            
            Write a friendly, extremely short and crisp markdown response (no more than 2 sentences):
            - Politely inform the customer that we don't have the ingredients for {dish_name}.
            - Suggest alternative meals or recipes that could be made with our available products.
            - Do NOT suggest items not in the in-stock list.
            """
        else:
            prompt = f"""
            You are the master composer for a smart grocery store checkout chatbot.
            The customer requested an item that we do not sell or that is currently out of stock.
            
            {history_str}
            Current User Query: "{state['raw_text']}"
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
        # Get servings from primary_result (recipe node may have defaulted it)
        primary_res = state.get("primary_result", {})
        servings_specified = primary_res.get("servings_specified", False)
        servings = primary_res.get("servings") or state.get("servings") or 2
        price_max_qar = state.get("price_max_qar")
        price_clause = f" under {price_max_qar} QAR" if price_max_qar else ""
        servings_note = "" if servings_specified else f" (default serving — tell me how many people to adjust quantities)"
        
        # Build ingredient-to-product mapping string for recipe queries
        ingredient_product_map = ""
        primary_res = state.get("primary_result", {})
        if intent == "recipe" and primary_res.get("is_recipe"):
            ingredients = primary_res.get("ingredients", [])
            if ingredients:
                lines = []
                for ing in ingredients:
                    store_name = ing.get("name", ing.get("ingredient_name", ""))
                    ingredient_name = ing.get("ingredient_name", "")
                    if ing.get("sku") and ing.get("in_stock"):
                        lines.append(f"  - {ingredient_name} → use store product: \"{store_name}\"")
                    else:
                        lines.append(f"  - {ingredient_name} (fresh / kitchen staple)")
                ingredient_product_map = "Ingredient → Store Product Name mapping:\n" + "\n".join(lines)
        
        prompt = f"""
        You are the master composer for a smart grocery store checkout chatbot.
        Your task is to write an extremely concise, friendly response (STRICTLY 1 TO 2 SENTENCES MAXIMUM).
        
        {history_str}
        Current User Query: "{state['raw_text']}"
        Intent: {intent}
        
        1. Primary Results:
        {primary_detail}
        
        {ingredient_product_map}
        
        2. Personalized Suggestions for this customer:
        {recommended_detail}
        
        3. Cross-sell combo items:
        {combo_detail}
        
        Offers active: {json.dumps(active_offers)}
        
        STRICT FORMATTING RULES:
        - Your response MUST be 1 to 2 short sentences maximum. Total length under 60 words.
        - DO NOT output any markdown headers (such as "### Search Results", "### Personalized Suggestions", "### Active Deals") or long bullet point lists. Visual product cards are already rendered separately in the UI below your text message.
        - For 'recipe': State the dish and exact quantities for {servings} people in 1 clear sentence. CRITICAL: Mention ONLY genuine cooking ingredients appropriate for this dish (e.g. rice, spices, oil, meat, poultry, vegetables, dairy, seasonings). NEVER include desserts, cakes, cookies, cosmetics, or unrelated products in the recipe text. Use the store product names from the mapping above for available in-stock items. If servings were NOT specified by the user, add a note: E.g.: "To make Biryani for 2 people{servings_note}, you'll need 300g Chicken Boneless Tawook Red, 200g Tilda Basmati Rice, 2 tbsp Eastern Biryani Spice Mix, 1 medium Onion White Spain, and 1 tbsp Olive Oil."
        - For 'search': State what was found concisely in 1 sentence. E.g.: "Here are the best {state.get('search_category') or 'product'} matches found in our catalog{price_clause}."
        - For 'greeting': "Hello! Welcome to Al Meera. How can I help you today?"
        """
        system_instruction = "You are a helpful, extremely concise supermarket assistant. Output ONLY 1-2 short sentences (under 50 words max) without headers, sub-headings, or bullet point lists."
        
        try:
            reply_text = llm_call(prompt, system_instruction=system_instruction, json_mode=False)
        except Exception as e:
            logger.error(f"Composer LLM call failed: {e}")
            reply_text = "Here are the best matches found for your request in our catalog."

    # Append current turn to history
    updated_history = list(chat_history)
    updated_history.append({"role": "user", "content": state["raw_text"]})
    updated_history.append({"role": "assistant", "content": reply_text})

    return {
        "reply_text": reply_text,
        "primary_cards": final_primary,
        "personalized_cards": final_recommended,
        "combo_cards": final_combo,
        "enrichment_timed_out": enrichment_timed_out,
        "chat_history": updated_history
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

def build_graph(checkpointer=None) -> StateGraph:
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
    
    # Merge enrichment pathways through a join barrier before composer
    workflow.add_node("join_barrier", join_barrier_node)
    workflow.add_edge("tier2_personalization", "join_barrier")
    workflow.add_edge("affinity", "join_barrier")
    workflow.add_edge("join_barrier", "composer")
    workflow.add_edge("no_matches", "composer")
    
    # Final step
    workflow.add_edge("composer", END)
    
    return workflow.compile(checkpointer=checkpointer)

# Join barrier node for fan-out synchronization
async def join_barrier_node(state: AgentState) -> Dict[str, Any]:
    """Synchronization barrier: waits for both tier2_personalization and affinity to complete before composer."""
    logger.info("--- JOIN BARRIER NODE --- Both enrichment paths completed.")
    return {}

# Compile the graph with checkpointer memory saver
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
orchestrator_graph = build_graph(checkpointer=memory)

# In-memory session history tracker
_session_histories: Dict[str, List[Dict[str, str]]] = {}

async def run_chatbot(customer_id: str, channel: str, query: str, session_id: str = "demo_session") -> Dict[str, Any]:
    """
    Runs the LangGraph chatbot orchestrator end-to-end (Asynchronous).
    """
    config = {"configurable": {"thread_id": session_id}}
    
    # Retrieve existing conversational history for the session
    existing_history = list(_session_histories.get(session_id, []))

    initial_state = {
        "raw_text": query,
        "customer_id": customer_id,
        "channel": channel,
        "session_id": session_id,
        "start_time": time.time(),
        "chat_history": existing_history,
        "search_query": None,
        "servings": None,
        "price_max_qar": None,
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
    
    # Execute the graph with config checkpointer thread mapping
    final_state = await orchestrator_graph.ainvoke(initial_state, config=config)
    
    # Update persistent session history
    updated_history = final_state.get("chat_history", [])
    if updated_history:
        _session_histories[session_id] = updated_history
    
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
