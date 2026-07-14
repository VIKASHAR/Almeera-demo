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
        groq_client = Groq(api_key=GROQ_API_KEY)
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

def run_groq(prompt, system_instruction=None, json_mode=False):
    """Calls Groq API using Llama 3.3 70B."""
    if not groq_client:
        raise ValueError("Groq client not configured")
        
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    
    # Try llama-3.3-70b-versatile, fallback to llama3-70b-8192
    model = "llama-3.3-70b-versatile"
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0.1,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"Groq call with {model} failed: {e}. Trying fallback model llama3-70b-8192.")
        try:
            response = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.1,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e2:
            logger.error(f"Groq fallback model also failed: {e2}")
            raise e2

def run_gemini(prompt, system_instruction=None, json_mode=False):
    """Calls Gemini API using gemini-1.5-flash or gemini-2.5-flash."""
    if not gemini_client:
        raise ValueError("Gemini client not configured")
        
    try:
        # Use gemini-1.5-flash as the fallback model
        generation_config = {}
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
            
        model = gemini_client.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            system_instruction=system_instruction
        )
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise e

def run_mock_llm(prompt, system_instruction="", json_mode=False):
    """
    Deterministic Mock LLM that returns coherent responses for the demo scripts
    if no API keys are present. This guarantees the demo will run out-of-the-box.
    """
    logger.info("Using MOCK LLM Responder (No API Keys provided or API call failed).")
    prompt_lower = prompt.lower()
    system_lower = system_instruction.lower() if system_instruction else ""
    
    # 1. JSON Mode (Router or Recipe Extractor)
    if json_mode:
        # Router classification
        if "classify" in system_lower or "intent" in system_lower or "router" in system_lower:
            recipe_keywords = ["recipe", "cook", "make", "how to", "suggest", "dinner", "lunch", "breakfast", "salad", "curry", "pasta", "sandwich"]
            is_recipe = any(w in prompt_lower for w in recipe_keywords)
            
            if is_recipe:
                dish_name = "Pasta Dinner"
                if "salad" in prompt_lower:
                    dish_name = "salad"
                elif "sandwich" in prompt_lower:
                    dish_name = "sandwich"
                elif "curry" in prompt_lower:
                    dish_name = "curry"
                return json.dumps({
                    "intent": "recipe", 
                    "category": None, 
                    "search_query": None, 
                    "dish_name": dish_name, 
                    "filters": {"attributes": {}, "price_max": None}
                })
            
            # Detect searched terms
            search_query = None
            category = None
            if "milk" in prompt_lower:
                search_query = "milk"
                category = "Dairy"
            elif "mushroom" in prompt_lower:
                search_query = "mushroom"
                category = "Produce"
            elif "avocado" in prompt_lower:
                search_query = "avocado"
                category = "Produce"
            elif "spinach" in prompt_lower:
                search_query = "spinach"
                category = "Produce"
            elif "tomato" in prompt_lower:
                search_query = "tomato"
                category = "Produce"
            elif "basil" in prompt_lower:
                search_query = "basil"
                category = "Produce"
            elif "garlic" in prompt_lower:
                search_query = "garlic"
                category = "Produce"
            elif "onion" in prompt_lower:
                search_query = "onion"
                category = "Produce"
            elif "banana" in prompt_lower:
                search_query = "banana"
                category = "Produce"
            elif "lemon" in prompt_lower:
                search_query = "lemon"
                category = "Produce"
            elif "bread" in prompt_lower:
                search_query = "bread"
                category = "Pantry/Grains"
            elif "rice" in prompt_lower:
                search_query = "rice"
                category = "Pantry/Grains"
            elif "curry" in prompt_lower:
                search_query = "curry"
                category = "Pantry/Grains"
            elif "chickpea" in prompt_lower:
                search_query = "chickpea"
                category = "Pantry/Grains"
            elif "pasta" in prompt_lower or "spaghetti" in prompt_lower or "penne" in prompt_lower:
                search_query = "pasta"
                category = "Pantry/Grains"
            elif "oil" in prompt_lower:
                search_query = "olive oil"
                category = "Pantry/Grains"
            elif "sauce" in prompt_lower:
                search_query = "sauce"
                category = "Pantry/Grains"
            elif "butter" in prompt_lower:
                search_query = "butter"
                category = "Dairy"
            elif "yogurt" in prompt_lower:
                search_query = "yogurt"
                category = "Dairy"
            elif "cheese" in prompt_lower:
                search_query = "cheese"
                category = "Dairy"
            elif "mango" in prompt_lower:
                search_query = "mango"
                category = "Produce"
            elif "orange" in prompt_lower or "juice" in prompt_lower:
                search_query = "orange juice"
                category = "Beverages"
                
            return json.dumps({
                "intent": "search", 
                "category": category, 
                "search_query": search_query, 
                "dish_name": None, 
                "filters": {"attributes": {}, "price_max": None}
            })
            
        # Recipe ingredients extractor
        if "recipe" in system_lower or "extractor" in system_lower:
            dish = "Pasta Dinner"
            if "salad" in prompt_lower:
                dish = "salad"
            elif "sandwich" in prompt_lower:
                dish = "sandwich"
            elif "curry" in prompt_lower:
                dish = "curry"
            return json.dumps({
                "dish_name": dish,
                "ingredients": ["Spaghetti Pasta", "Classic Tomato Sauce", "Roma Tomatoes", "Fresh Basil", "Fresh Garlic Bulb"]
            })
            
        return "{}"

    # 2. Text Mode (Composer)
    user_query = ""
    for line in prompt_lower.split('\n'):
        if "user query:" in line or "query:" in line:
            user_query = line.replace("user query:", "").replace("query:", "").strip()
            break
            
    search_target = user_query if user_query else prompt_lower
    
    # Check if fallback (no matches) is active
    is_unavailable = "do not sell" in prompt_lower or "out of stock" in prompt_lower or "unavailable" in prompt_lower
    
    if is_unavailable:
        item_name = "the requested item"
        if "mango" in search_target:
            item_name = "mangoes"
        elif "orange" in search_target or "juice" in search_target:
            item_name = "orange juice"
        elif "household" in search_target:
            item_name = "household items"
        elif "beverage" in search_target:
            item_name = "beverages"
        elif "snack" in search_target:
            item_name = "snacks"
            
        if "fruit" in search_target or "mango" in search_target or "produce" in search_target:
            alts = "Bananas Bunch, Roma Tomatoes, or Avocados Bag"
        elif "dairy" in search_target or "milk" in search_target:
            alts = "Organic Whole Milk, Greek Yogurt, or Cheddar Cheese Block"
        elif "juice" in search_target or "orange" in search_target or "beverage" in search_target:
            alts = "Almond Milk Unsweetened or Organic Coconut Milk"
        else:
            alts = "Roma Tomatoes, Organic Spinach, or Jasmine Rice"
            
        return f"I'm sorry, we don't have {item_name} in stock right now. However, you can find other fresh items like {alts} in our catalog!"
        
    # Standard responses
    if "spaghetti" in search_target or "pasta" in search_target:
        return (
            "Here is a simple **Pasta Dinner** recipe. Steps: Boil Spaghetti, sauté garlic/tomatoes with sauce, garnish with basil. "
            "Prego Tomato Sauce is 15% off and Barilla Spaghetti is 20% off today!"
        )
    elif "milk" in search_target:
        is_online = "online" in prompt_lower
        if is_online:
            return (
                "Our **Organic Low-Fat Milk (Lactaid)** is out of stock online. "
                "I recommend **Organic Whole Milk (Horizon)** or **Almond Milk Unsweetened (Silk)** as in-stock alternatives."
            )
        else:
            return (
                "I found **Organic Low-Fat Milk (Lactaid)** in stock in-store (5 units available). "
                "I've also suggested **Greek Yogurt Strawberry** (10% off!) as a personalized dairy pick."
            )
    elif "orange" in search_target or "juice" in search_target:
        return "I'm sorry, we don't carry fresh orange juice in our main database. However, we have other organic options like Almond Milk Unsweetened (Silk) or Organic Coconut Milk!"
    elif "is_greeting" in search_target or "intent: greeting" in search_target or "hello" in search_target or "hi" in search_target or "hey" in search_target:
        return (
            "Hello! Welcome to our Smart Supermarket. How can I help you today? "
            "I can assist with searching products, checking active store promotions, or suggesting recipes."
        )
    else:
        return "Here are the products matching your search request."


def llm_call(prompt, system_instruction=None, json_mode=False):
    """
    Orchestrator that calls Groq as primary, fallback to Gemini,
    and fallback to Mock LLM if all else fails.
    """
    if groq_client:
        try:
            return run_groq(prompt, system_instruction, json_mode)
        except Exception as e:
            logger.warning(f"Primary Groq LLM call failed, trying Gemini: {e}")
            
    if gemini_client:
        try:
            return run_gemini(prompt, system_instruction, json_mode)
        except Exception as e:
            logger.warning(f"Fallback Gemini LLM call failed: {e}")
            
    # If both client structures fail or are not initialized, use the Mock LLM
    return run_mock_llm(prompt, system_instruction, json_mode)
