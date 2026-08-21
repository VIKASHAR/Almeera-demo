import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import src.database as db

def audit():
    data_path = os.path.join(os.path.dirname(__file__), "test_analysis_results.json")
    with open(data_path, "r", encoding="utf-8") as f:
        tests = json.load(f)

    print("=" * 90)
    print("COMPREHENSIVE AUDIT: OUTPUT PRODUCTS vs. USER QUERY CONSTRAINTS")
    print("=" * 90)
    
    for t in tests:
        tid = t["id"]
        prompt = t["prompt"]
        cid = t["customer_id"]
        channel = t["channel"]
        intent = t.get("debug_trace", {}).get("intent", "unknown")
        primary_products = t.get("primary_products", [])
        primary_names = [p["name"] for p in primary_products]
        
        # Also fetch recommended and affinity product names
        rec_skus = t.get("recommended_skus", [])
        rec_prods = db.get_products_by_skus(rec_skus) if rec_skus else []
        rec_names = [p["name"] for p in rec_prods]
        
        aff_skus = t.get("affinity_skus", [])
        aff_prods = db.get_products_by_skus(aff_skus) if aff_skus else []
        aff_names = [p["name"] for p in aff_prods]
        
        print(f"\n[{tid}] Prompt: \"{prompt}\" (Customer: {cid}, Channel: {channel})")
        print(f"     Intent Classified: {intent}")
        print(f"     Primary Products ({len(primary_products)}):")
        if not primary_products:
            print(f"       -> [NO PRODUCTS RETURNED / OOS / GREETING]")
        for i, p in enumerate(primary_products, 1):
            price_qar = round(p.get('price', 0) * 3.64, 2)
            print(f"       {i}. {p['name']} | Cat: {p.get('category')} | Price: {price_qar} QAR (${p.get('price')})")
            
        print(f"     Recommendations (Top 3): {rec_names[:3]}")
        print(f"     Combos/Affinity (Top 3): {aff_names[:3]}")

if __name__ == "__main__":
    audit()
