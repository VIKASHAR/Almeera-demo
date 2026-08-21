import asyncio
import json
import os
import sys
import time

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import run_chatbot
import src.database as db

TEST_PROMPTS = [
    # 1. Simple search queries
    {"id": "T01", "name": "Basic search milk", "customer_id": "c1", "channel": "online", "prompt": "I need low-fat milk"},
    {"id": "T02", "name": "Basic search fresh fruits", "customer_id": "c1", "channel": "online", "prompt": "Do you have fresh fruits?"},
    {"id": "T03", "name": "Search fresh vegetables", "customer_id": "c2", "channel": "online", "prompt": "Show me fresh vegetables"},
    {"id": "T04", "name": "Search pet food with budget", "customer_id": "c3", "channel": "online", "prompt": "pet food under 15 QAR"},
    {"id": "T05", "name": "Search snacks with strict budget", "customer_id": "c3", "channel": "online", "prompt": "snacks under 5 QAR"},
    {"id": "T06", "name": "Search bread / bakery", "customer_id": "c1", "channel": "online", "prompt": "I want to buy sliced bread"},
    {"id": "T07", "name": "Search chicken meat", "customer_id": "c3", "channel": "online", "prompt": "fresh chicken breast"},
    {"id": "T08", "name": "Search beverage juice", "customer_id": "c1", "channel": "online", "prompt": "orange juice"},
    {"id": "T09", "name": "Search baby diapers", "customer_id": "c3", "channel": "online", "prompt": "baby diapers"},
    {"id": "T10", "name": "Search household detergent", "customer_id": "c3", "channel": "online", "prompt": "laundry detergent"},
    
    # 2. Recipe queries
    {"id": "T11", "name": "Recipe sandwich for 4", "customer_id": "c1", "channel": "online", "prompt": "i need to make sandwich for 4 people?"},
    {"id": "T12", "name": "Recipe chicken biryani unspecified servings", "customer_id": "c3", "channel": "online", "prompt": "give me a recipe for chicken biryani"},
    {"id": "T13", "name": "Recipe pasta dinner for 2 (vegan customer)", "customer_id": "c2", "channel": "online", "prompt": "suggest a pasta dinner for 2 people"},
    {"id": "T14", "name": "Recipe salad (low fat customer)", "customer_id": "c1", "channel": "online", "prompt": "how to make a healthy green salad"},
    {"id": "T15", "name": "Recipe pizza with servings", "customer_id": "c3", "channel": "online", "prompt": "recipe to make pizza for family of 4"},
    
    # 3. Personalization & Allergy constraints
    {"id": "T16", "name": "Nut allergy customer searching snacks", "customer_id": "c1", "channel": "online", "prompt": "find me some snacks or nuts"},
    {"id": "T17", "name": "Vegan customer searching dairy/cheese", "customer_id": "c2", "channel": "online", "prompt": "find cheese for pasta"},
    {"id": "T18", "name": "Low-fat customer searching dairy", "customer_id": "c1", "channel": "online", "prompt": "show me yogurt"},
    
    # 4. Out of stock / Channel difference / Non-existent items
    {"id": "T19", "name": "OOS item online vs in-store", "customer_id": "c1", "channel": "online", "prompt": "Luna Tomato Sauce"},
    {"id": "T20", "name": "In-store query for Skimmed Milk", "customer_id": "c1", "channel": "in_store", "prompt": "Skimmed Milk"},
    {"id": "T21", "name": "Non-existent exotic product", "customer_id": "c1", "channel": "online", "prompt": "do you sell dragon dragonfruit space spaceship?"},
    {"id": "T22", "name": "Non-existent recipe dish", "customer_id": "c1", "channel": "online", "prompt": "recipe for martian alien stew"},

    # 5. Greeting & Conversational edge cases
    {"id": "T23", "name": "Simple greeting", "customer_id": "c1", "channel": "online", "prompt": "hello there!"},
    {"id": "T24", "name": "Help inquiry", "customer_id": "c1", "channel": "online", "prompt": "what can you help me with?"},
    {"id": "T25", "name": "Budget edge case < 2 QAR", "customer_id": "c3", "channel": "online", "prompt": "show me items under 2 QAR"},
    
    # 6. Multi-turn dialogue context
    {"id": "T26a", "name": "Multi-turn Step 1", "customer_id": "c1", "channel": "online", "prompt": "Do you have pasta?", "session_id": "multiturn_1"},
    {"id": "T26b", "name": "Multi-turn Step 2 (Pronoun reference)", "customer_id": "c1", "channel": "online", "prompt": "Can you give me a recipe to cook it for 4 people?", "session_id": "multiturn_1"},
]

async def run_all_tests():
    results = []
    print(f"Starting test run with {len(TEST_PROMPTS)} prompt scenarios...\n")
    
    for item in TEST_PROMPTS:
        session_id = item.get("session_id", f"session_{item['id']}")
        t0 = time.time()
        try:
            res = await run_chatbot(
                customer_id=item["customer_id"],
                channel=item["channel"],
                query=item["prompt"],
                session_id=session_id
            )
            elapsed = time.time() - t0
            
            # Fetch product details for primary SKUs to check quality
            primary_skus = res.get("structured", {}).get("primary_skus", [])
            primary_prods = db.get_products_by_skus(primary_skus) if primary_skus else []
            
            rec_skus = res.get("structured", {}).get("recommended_skus", [])
            rec_prods = db.get_products_by_skus(rec_skus) if rec_skus else []
            
            aff_skus = res.get("structured", {}).get("affinity_skus", [])
            aff_prods = db.get_products_by_skus(aff_skus) if aff_skus else []
            
            entry = {
                "id": item["id"],
                "name": item["name"],
                "customer_id": item["customer_id"],
                "channel": item["channel"],
                "prompt": item["prompt"],
                "session_id": session_id,
                "elapsed_sec": round(elapsed, 2),
                "reply_text": res.get("text", ""),
                "debug_trace": res.get("debug_trace", {}),
                "primary_skus": primary_skus,
                "primary_products": [{"sku": p["sku"], "name": p["name"], "category": p.get("category"), "price": p.get("price")} for p in primary_prods],
                "recommended_skus": rec_skus,
                "affinity_skus": aff_skus,
                "error": None
            }
            print(f"[{item['id']}] {item['name']}: {elapsed:.2f}s | Intent: {res.get('debug_trace', {}).get('intent')} | Primary SKUs: {len(primary_skus)}")
            print(f"    Reply: {res.get('text', '')[:100]}...")
            if primary_prods:
                print(f"    Products: {[p['name'] for p in primary_prods[:3]]}")
            print()
            results.append(entry)
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[{item['id']}] {item['name']} FAILED: {e}")
            results.append({
                "id": item["id"],
                "name": item["name"],
                "customer_id": item["customer_id"],
                "channel": item["channel"],
                "prompt": item["prompt"],
                "session_id": session_id,
                "elapsed_sec": round(elapsed, 2),
                "error": str(e)
            })
            
    # Save full results
    out_path = os.path.join(os.path.dirname(__file__), "test_analysis_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll tests completed. Full output saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
