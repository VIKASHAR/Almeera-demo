import pytest
import os
import sqlite3
import json
import sys

# Add src and db to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.database as db
from db.seed import seed_database

TEST_DB_PATH = "db/test_demo.db"

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Setup test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Use monkeypatch-equivalent approach for module-scoped fixture
    original_db_path = db.DB_PATH
    db.DB_PATH = os.path.abspath(TEST_DB_PATH)
    seed_database(TEST_DB_PATH, "db/schema.sql")
    
    yield
    
    # Restore original DB_PATH and cleanup test database
    db.DB_PATH = original_db_path
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_search_products():
    # Search all produce
    results = db.search_products(category="Produce")
    assert len(results) > 0
    categories = {r["category"] for r in results}
    assert categories == {"Produce"}
    
    # Search for low-fat dairy
    results_lf = db.search_products(category="Dairy", attributes={"fat_content": "low-fat"})
    assert len(results_lf) > 0
    for r in results_lf:
        assert r["attributes_json"]["fat_content"] == "low-fat"

def test_get_alternatives():
    # SKU '6281020101111' (Luna Tomato Sauce) is seeded as out of stock in both channels
    alt_online = db.get_alternatives("6281020101111", in_stock_only=True, channel="online")
    assert len(alt_online) > 0
    # Alternatives should be in the same subcategory or category and in stock
    for alt in alt_online:
        assert alt["sku"] != "6281020101111"
        assert alt["stock_qty"] > 0

def test_check_inventory():
    stock = db.check_inventory(["3043931692415", "5255010204428"], channel="online")
    # Skimmed Milk should have 0 online stock (seeded custom test case)
    assert stock.get("3043931692415") == 0
    # Full Cream Milk should be in stock
    assert stock.get("5255010204428", 0) > 0
    
    # Check in-store channel where Skimmed Milk has 5 stock
    store_stock = db.check_inventory(["3043931692415", "5255010204428"], channel="in_store")
    assert store_stock.get("3043931692415") == 5

def test_get_active_offers():
    offers = db.get_active_offers(["5000157026224", "6281020101111"])
    assert len(offers) > 0
    skus = {o["sku"] for o in offers}
    assert "5000157026224" in skus or "6281020101111" in skus

def test_map_ingredients_to_skus():
    mapping = db.map_ingredients_to_skus(["spaghetti", "tomatoes", "low-fat milk"])
    assert mapping["spaghetti"] is not None
    assert mapping["spaghetti"]["sku"] == "5000157026224" or "spaghetti" in mapping["spaghetti"]["name"].lower()
    assert mapping["tomatoes"] is not None
    assert "tomato" in mapping["tomatoes"]["name"].lower() or mapping["tomatoes"]["subcategory"] == "Tomatoes"
    assert mapping["low-fat milk"] is not None
    assert mapping["low-fat milk"]["sku"] == "3043931692415" or "milk" in mapping["low-fat milk"]["name"].lower()

def test_get_customer_recommendations():
    # Customer Alice (c1) prefers low-fat, dairy
    recs_alice = db.get_customer_recommendations("c1", "Dairy")
    assert len(recs_alice) > 0
    for r in recs_alice:
        # Check low-fat filter works for Dairy
        assert r["attributes_json"]["fat_content"] == "low-fat"

    # Customer Bob (c2) prefers vegan
    recs_bob = db.get_customer_recommendations("c2")
    assert len(recs_bob) > 0
    for r in recs_bob:
        # Check vegan filter works
        assert r["attributes_json"].get("vegan") is not False

def test_get_affinity():
    # Spaghetti ('5000157026224') should trigger affinity recommendations
    recs = db.get_affinity(["5000157026224"], top_n=2)
    assert len(recs) > 0, "Affinity should return at least one recommendation"
    skus = [r["sku"] for r in recs]
    # Structural assertions: results should not include the input SKU
    assert "5000157026224" not in skus, "Affinity results should not include the input SKU"
    # Each result should have required fields
    for r in recs:
        assert "sku" in r
        assert "name" in r
        assert "confidence" in r
        assert r["confidence"] > 0

def test_get_customer_profile():
    profile = db.get_customer_profile("c1")
    assert profile["dietary_preference"] == "low-fat"
    assert "nuts" in profile["avoid_list"]

def test_generic_pet_search():
    # Searching for pet food / category Pet should yield pet items
    results = db.search_products(category="Pet", query_str="pet food")
    assert len(results) > 0
    for r in results:
        assert r["category"] == "Pet"

def test_price_max_filter():
    # 15 QAR = ~4.12 USD
    usd_max = round(15.0 / 3.64, 2)
    results = db.search_products(price_max=usd_max)
    assert len(results) > 0
    for r in results:
        assert r["price"] <= usd_max

def test_ingredient_quantity_mapping():
    # Quantities like '4 slices', '400g' should be stripped for catalog lookup
    mapping = db.map_ingredients_to_skus(["4 slices bread", "400g chicken breast", "1 head lettuce"])
    assert mapping["4 slices bread"] is not None
    assert mapping["400g chicken breast"] is not None
    assert mapping["1 head lettuce"] is not None

def test_skimmed_milk_attribute_normalization():
    # Skimmed milk with non-fat or low-fat filter in-store
    results = db.search_products(category="Dairy", query_str="skimmed milk", attributes={"fat_content": "non-fat"}, channel="in_store")
    assert len(results) > 0
    for r in results:
        assert r["attributes_json"]["fat_content"] in ("low-fat", "non-fat")
        assert r["stock_qty"] > 0

def test_pure_budget_query():
    # Searching under 2 QAR (~0.55 USD) without query_str
    usd_max = round(2.0 / 3.64, 4)
    results = db.search_products(price_max=usd_max, channel="online")
    assert len(results) > 0
    for r in results:
        assert r["price"] <= usd_max
        assert r["stock_qty"] > 0

def test_ingredient_semantic_blocking():
    # Sandwich bread should not map to breadcrumbs
    mapping = db.map_ingredients_to_skus(["8 slices bread", "2 tbsp lemon juice", "200g mixed salad greens", "600g pizza dough"])
    
    bread_item = mapping.get("8 slices bread")
    assert bread_item is not None
    assert "crumb" not in bread_item["name"].lower()
    
    lemon_item = mapping.get("2 tbsp lemon juice")
    assert lemon_item is not None
    assert "jelly" not in lemon_item["name"].lower()
    assert "dessert" not in lemon_item["name"].lower()
    
    salad_item = mapping.get("200g mixed salad greens")
    if salad_item:
        assert "fatayer" not in salad_item["name"].lower()
        assert "pastry" not in salad_item["name"].lower()

    pizza_item = mapping.get("600g pizza dough")
    if pizza_item:
        assert "pizza vegetable" not in pizza_item["name"].lower()

def test_vegan_cheese_filtering():
    profile = {"dietary_preference": "vegan", "avoid_list": [], "preferred_brands": []}
    from src.graph import is_product_compliant
    # Regular dairy cheese should not be compliant for vegan
    dairy_cheese = {"category": "Dairy", "name": "Emborg Swiss Sliced Cheese", "attributes_json": {"vegan": True, "dairy_free": False}}
    assert is_product_compliant(dairy_cheese, profile) is False
    
    # Plant-based vegan cheese should be compliant
    vegan_cheese = {"category": "Dairy", "name": "Milky Lux Vegan Gouda Cheese", "attributes_json": {"vegan": True, "dairy_free": True}}
    assert is_product_compliant(vegan_cheese, profile) is True



