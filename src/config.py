import os
import json
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Standardize keys: treat placeholders as empty
if GROQ_API_KEY.startswith("your_") or not GROQ_API_KEY.strip():
    GROQ_API_KEY = ""
if GEMINI_API_KEY.startswith("your_") or not GEMINI_API_KEY.strip():
    GEMINI_API_KEY = ""

# Initialize clients if keys exist
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY, max_retries=0)
        logger.info("Groq client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")

gemini_client = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_client = genai
        logger.info("Gemini client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")

# Active / preferred Groq model list (prefer models without reasoning prefix for clean JSON output)
PREFERRED_GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "allam-2-7b",
    "qwen/qwen3.6-27b"
]
_working_groq_model = None

def _get_working_groq_model():
    global _working_groq_model
    if _working_groq_model is not None:
        return _working_groq_model
    if not groq_client:
        return None
    try:
        available = [m.id for m in groq_client.models.list().data]
        for pref in PREFERRED_GROQ_MODELS:
            if pref in available:
                _working_groq_model = pref
                logger.info(f"Selected working Groq model: {_working_groq_model}")
                return _working_groq_model
        if available:
            # Pick first available text generation model
            _working_groq_model = available[0]
            return _working_groq_model
    except Exception as e:
        logger.warning(f"Failed to query Groq models: {e}")
    _working_groq_model = False
    return None

def run_groq(prompt, system_instruction=None, json_mode=False):
    """Calls Groq API using discovered working model."""
    if not groq_client:
        raise ValueError("Groq client not configured")
        
    model = _get_working_groq_model()
    if not model:
        raise ValueError("No compatible Groq model available")
        
    sys_inst = system_instruction or "You are a helpful assistant."
    user_prompt = prompt
    if json_mode:
        if "json" not in sys_inst.lower():
            sys_inst += " Respond strictly in valid JSON format."
        if "json" not in user_prompt.lower():
            user_prompt += "\nRespond strictly in valid JSON format."
        
    messages = [
        {"role": "system", "content": sys_inst},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0.1,
            max_tokens=1024
        )
        content = response.choices[0].message.content or ""
        # Filter out think tags if present
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        if content:
            return content
        raise ValueError("Empty response from Groq model")
    except Exception as e:
        logger.warning(f"Groq call with {model} failed: {e}")
        raise e

def run_gemini(prompt, system_instruction=None, json_mode=False):
    """Calls Gemini API using gemini-2.5-flash with gemini-1.5-flash fallback."""
    if not gemini_client:
        raise ValueError("Gemini client not configured")
        
    generation_config = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"
        
    for model_name in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-flash-latest"]:
        try:
            model = gemini_client.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            logger.warning(f"Gemini call with {model_name} failed: {e}")
            continue
            
    raise ValueError("All Gemini models failed")

def run_mock_llm(prompt, system_instruction="", json_mode=False):
    """
    Deterministic Mock LLM that returns coherent responses for the demo scripts
    if no API keys are present or rate limits hit.
    """
    import re as _re
    logger.info("Using MOCK LLM Responder (No API Keys provided or API call failed).")
    prompt_lower = prompt.lower().replace("briyani", "biryani").replace("biriyani", "biryani")
    system_lower = system_instruction.lower() if system_instruction else ""
    
    # 1. JSON Mode (Router or Recipe Extractor)
    if json_mode:
        # --- INTENT ROUTER ---
        if any(kw in system_lower for kw in ["classify", "intent", "router", "categorize", "detect"]):
            recipe_keywords = [
                "recipe", "cook", "make", "how to", "suggest", "dinner", "lunch", "breakfast",
                "salad", "curry", "pasta", "sandwich", "biryani", "briyani", "biriyani", "pizza", "burger", "soup",
                "prepare", "ingredients for", "need to make", "want to make"
            ]
            is_recipe = any(w in prompt_lower for w in recipe_keywords)
            
            # Extract servings from prompt
            extracted_servings = None
            servings_patterns = [
                r'(?:for|serve[sd]?|serving[s]?|family\s+of)\s+(\d+)\s*(?:people|persons?|servings?|guests?|adults?)?',
                r'(\d+)\s+(?:people|persons?|servings?|guests?|adults?)',
            ]
            for pat in servings_patterns:
                sm = _re.search(pat, prompt_lower)
                if sm:
                    try:
                        candidate = int(sm.group(1))
                        if 1 <= candidate <= 50:
                            extracted_servings = candidate
                            break
                    except Exception:
                        pass
            
            # Extract price from prompt dynamically
            extracted_price_qar = None
            price_pats = [
                r'(?:under|below|less\s+than|cheaper\s+than|max(?:imum)?(?:\s+price)?|no\s+more\s+than)\s*(\d+(?:\.\d+)?)\s*(?:qar|riyals?)?',
                r'<\s*(\d+(?:\.\d+)?)\s*(?:qar|riyals?)?',
                r'(\d+(?:\.\d+)?)\s*(?:qar|riyals?)\s+(?:or\s+)?(?:less|under|below|max)',
            ]
            for pat in price_pats:
                pm = _re.search(pat, prompt_lower)
                if pm:
                    try:
                        extracted_price_qar = float(pm.group(1))
                        break
                    except Exception:
                        pass
            extracted_price_usd = round(extracted_price_qar / 3.64, 4) if extracted_price_qar else None
            
            if is_recipe:
                # Determine dish name from expanded keyword list
                dish_name = None
                dish_keywords = [
                    "sandwich", "salad", "curry", "biryani", "pizza", "burger", "soup",
                    "pasta", "rice", "steak", "chicken", "fish", "omelette", "omelet",
                    "pancake", "smoothie", "wrap", "taco", "noodle", "stir fry",
                    "breakfast", "lunch", "dinner", "meal"
                ]
                for d in dish_keywords:
                    if d in prompt_lower:
                        dish_name = d.capitalize()
                        break
                if not dish_name:
                    # Contextual fallback: use the most meaningful noun from the query
                    dish_name = "Meal"
                return json.dumps({
                    "intent": "recipe",
                    "category": None,
                    "search_query": None,
                    "dish_name": dish_name,
                    "servings": extracted_servings or 2,
                    "price_max_qar": extracted_price_qar,
                    "filters": {"attributes": {}, "price_max": extracted_price_usd}
                })
            
            # --- SEARCH CATEGORY MAPPING ---
            # Full keyword → category table
            category_map = [
                # Produce (check BEFORE Meat to avoid "fresh chicken" → Produce)
                ("Produce", ["banana", "apple", "mango", "avocado", "lemon", "orange", "grape",
                             "watermelon", "pineapple", "kiwi", "strawberry", "peach", "pear",
                             "tomato", "spinach", "lettuce", "cucumber", "carrot", "onion", "garlic",
                             "pepper", "mushroom", "broccoli", "vegetable", "veggie", "fruit",
                             "fresh fruit", "fresh vegetable", "produce"]),
                # Meat & Seafood (check BEFORE generic "fresh")
                ("Meat & Seafood", ["chicken", "beef", "lamb", "mutton", "fish", "seafood",
                                    "shrimp", "prawn", "turkey", "drumstick", "meat", "steak",
                                    "mince", "minced", "breast", "thigh"]),
                # Dairy
                ("Dairy", ["milk", "cheese", "yogurt", "butter", "laban", "cream", "ghee",
                            "sour cream", "cream cheese", "skimmed", "full cream", "dairy"]),
                # Bakery
                ("Bakery", ["bread", "croissant", "pastry", "baguette", "pita", "flatbread",
                             "toast", "loaf", "bun", "roll", "bakery"]),
                # Beverages
                ("Beverages", ["juice", "soda", "water", "coffee", "tea", "drink", "beverage",
                                "cola", "sprite", "pepsi", "energy drink", "smoothie"]),
                # Snacks
                ("Snacks", ["chips", "crisp", "cookie", "biscuit", "snack", "chocolate", "candy",
                             "sweet", "nut", "almond", "cashew", "cracker", "popcorn", "wafer"]),
                # Pantry/Grains
                ("Pantry/Grains", ["rice", "pasta", "noodle", "sauce", "olive oil", "oil", "spice",
                                    "flour", "canned", "beans", "chickpea", "coconut milk", "curry",
                                    "cereal", "oat", "grain"]),
                # Pet
                ("Pet", ["cat food", "dog food", "pet food", "whiskas", "friskies", "pedigree",
                          "purina", "cat litter", "pet supply", "pet"]),
                # Baby
                ("Baby", ["baby food", "diaper", "nappy", "wipes", "baby", "infant"]),
                # Household
                ("Household", ["cleaning", "detergent", "laundry", "tissue", "dishwash",
                                "soap", "bleach", "household", "hygiene", "trash bag"]),
                # Personal Care
                ("Personal Care", ["shampoo", "conditioner", "shower gel", "toothpaste",
                                    "deodorant", "personal care", "oral", "lotion"]),
            ]
            
            search_query = None
            category = None
            for cat, keywords in category_map:
                if any(kw in prompt_lower for kw in keywords):
                    category = cat
                    # Set a clean search_query from the first matching keyword
                    for kw in keywords:
                        if kw in prompt_lower:
                            search_query = kw
                            break
                    break
            
            return json.dumps({
                "intent": "search",
                "category": category,
                "search_query": search_query,
                "dish_name": None,
                "servings": None,
                "price_max_qar": extracted_price_qar,
                "filters": {"attributes": {}, "price_max": extracted_price_usd}
            })
            
        # --- RECIPE INGREDIENTS EXTRACTOR ---
        if any(kw in system_lower for kw in ["recipe", "extractor", "ingredient", "chef", "dish", "cook"]):
            # Extract servings (default 2, not 4)
            extracted_servings = 2
            for pat in [r'for\s+(\d+)\s*people', r'(\d+)\s+people', r'serves?\s+(\d+)']:
                sm = _re.search(pat, prompt_lower)
                if sm:
                    try:
                        extracted_servings = max(1, int(sm.group(1)))
                        break
                    except Exception:
                        pass
            s = extracted_servings
            
            # Comprehensive recipe ingredient lists (scaled to servings)
            # Detect dietary constraints from the prompt/system instruction
            is_vegan = "vegan" in prompt_lower or "vegan" in system_lower
            is_low_fat = "low-fat" in prompt_lower or "low fat" in prompt_lower or "low-fat" in system_lower
            is_gluten_free = "gluten-free" in prompt_lower or "gluten free" in prompt_lower or "gluten-free" in system_lower
            has_nut_allergy = "nuts" in prompt_lower and ("avoid" in prompt_lower or "allerg" in prompt_lower or "not include" in prompt_lower)
            
            # Base recipe ingredients (scaled to servings)
            if is_vegan:
                recipe_ingredients = {
                    "sandwich": [
                        f"{s * 2} slices Sliced White Bread",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} head Lettuce",
                        f"{max(1, s // 2)} Avocado"
                    ],
                    "pasta": [
                        f"{s * 100}g Spaghetti Pasta",
                        f"{max(1, s // 2)} jar Tomato Sauce",
                        f"{s} Roma Tomatoes",
                        "2 tbsp Olive Oil"
                    ],
                    "salad": [
                        f"{max(1, s // 2)} head Lettuce",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} Cucumber",
                        f"{max(1, s // 4) * 50}ml Afia Extra Virgin Olive Oil"
                    ],
                    "curry": [
                        f"{s * 100}g Chickpeas",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} Onion",
                        f"2 tbsp Curry Powder",
                        f"{max(1, s // 2)} cup Basmati Rice"
                    ],
                    "biryani": [
                        f"{s * 100}g Chickpeas",
                        f"{s * 100}g Basmati Rice",
                        f"{max(1, s // 2)} Onion",
                        "2 tbsp Biryani Spice Mix",
                        "2 tbsp Olive Oil"
                    ],
                    "pizza": [
                        f"{max(1, s // 2)} Pizza Base",
                        f"{max(1, s // 2)} jar Tomato Sauce",
                        f"{s} Tomatoes",
                        "2 tbsp Olive Oil"
                    ],
                    "burger": [
                        f"{s} Burger Buns",
                        f"{s * 100}g Chickpeas",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} head Lettuce"
                    ],
                    "soup": [
                        f"{s * 100}g Chickpeas",
                        f"{s} Carrot",
                        f"{max(1, s // 2)} Onion",
                        "2 tbsp Olive Oil"
                    ],
                    "rice": [
                        f"{s * 100}g Basmati Rice",
                        "2 tbsp Afia Extra Virgin Olive Oil",
                        f"{max(1, s // 2)} Onion",
                        "Salt and Spices"
                    ],
                }
            else:
                recipe_ingredients = {
                    "sandwich": [
                        f"{s * 2} slices Sliced White Bread",
                        f"{s * 100}g Chicken Breast",
                        f"{max(1, s // 2)} head Lettuce",
                        f"{s} Tomatoes"
                    ],
                    "pasta": [
                        f"{s * 100}g Spaghetti Pasta",
                        f"{max(1, s // 2)} jar Tomato Sauce",
                        f"{s} Roma Tomatoes",
                        "Fresh Basil"
                    ],
                    "salad": [
                        f"{max(1, s // 2)} head Lettuce",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} Cucumber",
                        f"{max(1, s // 4) * 50}ml Afia Extra Virgin Olive Oil"
                    ],
                    "curry": [
                        f"{s * 150}g Chicken",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} Onion",
                        f"2 tbsp Curry Powder",
                        f"{max(1, s // 2)} cup Basmati Rice"
                    ],
                    "biryani": [
                        f"{s * 150}g Chicken",
                        f"{s * 100}g Basmati Rice",
                        f"{max(1, s // 2)} Onion",
                        "2 tbsp Biryani Spice Mix",
                        f"{max(1, s // 4) * 50}ml Plain Yogurt"
                    ],
                    "pizza": [
                        f"{max(1, s // 2)} Pizza Base",
                        f"{s * 50}g Mozzarella Cheese",
                        f"{max(1, s // 2)} jar Luna Tomato Sauce",
                        f"{s * 50}g Chicken"
                    ],
                    "burger": [
                        f"{s} Burger Buns",
                        f"{s * 150}g Beef Mince",
                        f"{s} Tomatoes",
                        f"{max(1, s // 2)} head Lettuce",
                        f"{s} slices Cheese"
                    ],
                    "soup": [
                        f"{s * 100}g Chicken",
                        f"{s} Carrot",
                        f"{max(1, s // 2)} Onion",
                        "2 tbsp Olive Oil",
                        "Salt and Pepper"
                    ],
                    "rice": [
                        f"{s * 100}g Basmati Rice",
                        "2 tbsp Afia Extra Virgin Olive Oil",
                        f"{max(1, s // 2)} Onion",
                        "Salt and Spices"
                    ],
                }
            
            dish = None
            ingredients = None
            for d_key, d_ings in recipe_ingredients.items():
                if d_key in prompt_lower:
                    dish = d_key.capitalize()
                    ingredients = d_ings
                    break
            if not dish:
                # Contextual fallback instead of always "Pasta Dinner"
                dish = "Meal"
                ingredients = recipe_ingredients["pasta"]
            
            return json.dumps({
                "dish_name": dish,
                "servings": extracted_servings,
                "ingredients": ingredients
            })
            
        return "{}"

    # 2. Text Mode (Composer)
    user_query = ""
    for line in prompt_lower.split('\n'):
        if "user query:" in line or "query:" in line:
            user_query = line.replace("user query:", "").replace("query:", "").strip().strip('"')
            break
            
    search_target = user_query if user_query else prompt_lower
    
    # Check if fallback (no matches) is active
    is_unavailable = "do not sell" in prompt_lower or "out of stock" in prompt_lower or "unavailable" in prompt_lower
    
    if is_unavailable:
        item_name = "the requested item"
        if "mango" in search_target:
            item_name = "mangoes"
        elif "orange juice" in search_target or "oj" in search_target:
            item_name = "orange juice"
        elif "household" in search_target:
            item_name = "household items"
        elif "beverage" in search_target or "drink" in search_target:
            item_name = "beverages"
        elif "snack" in search_target:
            item_name = "snacks"
            
        if "fruit" in search_target or "mango" in search_target or "produce" in search_target:
            alts = "Banana Ecuador, Avocado Kenya, or Lemon Egypt"
        elif "dairy" in search_target or "milk" in search_target:
            alts = "Al Maha Plain Yogurt Low Fat, Al Badia Full Cream Milk Powder, or Regilait Skimmed Milk"
        elif "juice" in search_target or "orange" in search_target or "beverage" in search_target:
            alts = "other fresh produce items like Banana Ecuador or Avocado Kenya"
        elif "snack" in search_target:
            alts = "other available items in our catalog"
        else:
            alts = "Banana Ecuador, Roma Tomatoes, or Al Maha Plain Yogurt Low Fat"
            
        return f"I'm sorry, we don't have {item_name} in stock right now. You can find other fresh items like {alts} in our catalog!"
        
    # Standard composer responses
    if any(w in search_target for w in ["sandwich", "recipe", "salad", "curry", "pasta", "biryani", "pizza"]):
        return "Here are the best ingredients found in our catalog to prepare your dish — check the cards below for product details and prices."
    elif "bread" in search_target:
        return "Here are the best fresh bread choices found in our store catalog."
    elif any(w in search_target for w in ["pet", "cat", "dog"]):
        price_hint = ""
        pm = _re.search(r'under\s+(\d+)', search_target)
        if pm:
            price_hint = f" under {pm.group(1)} QAR"
        return f"Here are the best pet food options found in our store catalog{price_hint}."
    elif any(w in search_target for w in ["fruit", "vegetable", "veggie", "produce", "banana", "avocado", "lemon", "tomato"]):
        return "Here are the best fresh Produce matches found in our catalog, including fruits and vegetables."
    elif any(w in search_target for w in ["snack", "chips", "cookie", "chocolate"]):
        price_hint = ""
        pm = _re.search(r'under\s+(\d+)', search_target)
        if pm:
            price_hint = f" under {pm.group(1)} QAR"
        return f"Here are the best Snack matches found in our catalog{price_hint}."
    elif any(w in search_target for w in ["milk", "cheese", "yogurt", "butter", "dairy"]):
        return "Here are the best Dairy matches found in our catalog."
    elif any(w in search_target for w in ["chicken", "beef", "meat", "fish", "seafood"]):
        return "Here are the best Meat & Seafood matches found in our catalog."
    elif any(w in search_target for w in ["greeting", "hello", "hi", "hey"]):
        return "Hello! Welcome to Al Meera. How can I help you today?"
    else:
        return "Here are the best product matches found in our catalog for your request."


def llm_call(prompt, system_instruction=None, json_mode=False):
    """
    Orchestrator that calls Gemini as primary (fast, reliable JSON and schema compliance),
    with fallback to Groq, and finally Mock LLM.
    """
    if gemini_client:
        try:
            return run_gemini(prompt, system_instruction, json_mode)
        except Exception as e:
            logger.warning(f"Primary Gemini LLM call failed, trying Groq: {e}")
            
    if groq_client:
        try:
            return run_groq(prompt, system_instruction, json_mode)
        except Exception as e:
            logger.warning(f"Fallback Groq LLM call failed: {e}")
            
    # If both client structures fail or are not initialized, use the Mock LLM
    return run_mock_llm(prompt, system_instruction, json_mode)
