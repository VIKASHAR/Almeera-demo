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
        
    db.DB_PATH = os.path.abspath(TEST_DB_PATH)
    seed_database(TEST_DB_PATH, "db/schema.sql")
    
    yield
    
    # Cleanup test database
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
    # Spaghetti ('5000157026224') should trigger items in the same pasta basket due to our seeded transactions
    recs = db.get_affinity(["5000157026224"], top_n=2)
    assert len(recs) > 0
    skus = [r["sku"] for r in recs]
    pasta_basket = {"6281020101111", "9911054000000", "8006830991763", "9910815000000", "6281011135897"}
    for sku in skus:
        assert sku in pasta_basket

def test_get_customer_profile():
    profile = db.get_customer_profile("c1")
    assert profile["dietary_preference"] == "low-fat"
    assert "nuts" in profile["avoid_list"]

