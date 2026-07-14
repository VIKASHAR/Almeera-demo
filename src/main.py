from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import logging

# Add workspace to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph import run_chatbot
from db.seed import seed_database
import src.database as db

logger = logging.getLogger(__name__)

app = FastAPI(title="Grocery Smart Chatbot Backend", version="1.0.0")

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    raw_text: str
    customer_id: str
    channel: str # 'online' | 'in_store'
    session_id: str = "demo_session"

class ProductsRequest(BaseModel):
    skus: list[str]

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        logger.info(f"Received chat request from customer={req.customer_id} on channel={req.channel} session={req.session_id}: '{req.raw_text}'")
        result = await run_chatbot(req.customer_id, req.channel, req.raw_text, req.session_id)
        return result
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/seed")
def seed_endpoint():
    try:
        db_path = "db/mvp_demo.db"
        schema_path = "db/schema.sql"
        seed_database(db_path, schema_path)
        return {"status": "success", "message": "Database reset and seeded successfully."}
    except Exception as e:
        logger.error(f"Error seeding database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/products/details")
def get_products_details(req: ProductsRequest):
    """
    Fetches full product details for a list of SKUs, including stock and active promotions.
    """
    try:
        if not req.skus:
            return []
            
        conn = db.get_connection()
        conn.row_factory = db.dict_factory
        cursor = conn.cursor()
        
        # Query products
        placeholders = ",".join("?" for _ in req.skus)
        query = f"SELECT * FROM products WHERE sku IN ({placeholders})"
        cursor.execute(query, req.skus)
        products = cursor.fetchall()
        
        # Get active promotions
        offers = db.get_active_offers(req.skus)
        offer_map = {o['sku']: o for o in offers}
        
        # Get stock quantities for both online and in-store
        stock_query = f"SELECT sku, channel, stock_qty FROM inventory WHERE sku IN ({placeholders})"
        cursor.execute(stock_query, req.skus)
        stock_rows = cursor.fetchall()
        
        stock_map = {}
        for row in stock_rows:
            sku = row['sku']
            if sku not in stock_map:
                stock_map[sku] = {}
            stock_map[sku][row['channel']] = row['stock_qty']
            
        conn.close()
        
        # Merge details
        for p in products:
            sku = p['sku']
            p['stock'] = stock_map.get(sku, {"online": 0, "in_store": 0})
            p['promotion'] = None
            if sku in offer_map:
                promo = offer_map[sku]
                p['promotion'] = {
                    "discount_pct": promo['discount_pct'],
                    "description": promo['description']
                }
                
        return products
    except Exception as e:
        logger.error(f"Error fetching product details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/customers")
def list_customers():
    """
    List customers and their details for the frontend profile selector.
    """
    try:
        conn = db.get_connection()
        conn.row_factory = db.dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT customer_id, name, preferences_json FROM customers")
        customers = cursor.fetchall()
        conn.close()
        return customers
    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
def get_products(category: str = None, search: str = None, channel: str = 'online'):
    try:
        products = db.search_products(category=category, query_str=search, channel=channel, limit=100)
        # Merge promotions
        skus = [p['sku'] for p in products]
        if skus:
            offers = db.get_active_offers(skus)
            offer_map = {o['sku']: o for o in offers}
            for p in products:
                sku = p['sku']
                p['promotion'] = None
                if sku in offer_map:
                    promo = offer_map[sku]
                    p['promotion'] = {
                        "discount_pct": promo['discount_pct'],
                        "description": promo['description']
                    }
        return products
    except Exception as e:
        logger.error(f"Error listing products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{sku}")
def get_product_detail(sku: str, channel: str = 'online'):
    try:
        # Get product directly by SKU to avoid full-table scan
        conn = db.get_connection()
        conn.row_factory = db.dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
        product = cursor.fetchone()
        conn.close()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
            
        # Get promotions
        offers = db.get_active_offers([sku])
        product['promotion'] = None
        if offers:
            promo = offers[0]
            product['promotion'] = {
                "discount_pct": promo['discount_pct'],
                "description": promo['description']
            }
            
        # Get stock for both channels
        conn = db.get_connection()
        conn.row_factory = db.dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT channel, stock_qty FROM inventory WHERE sku = ?", (sku,))
        stock_rows = cursor.fetchall()
        product['stock'] = {row['channel']: row['stock_qty'] for row in stock_rows}
        conn.close()
        
        # Get alternatives as recommendations
        alternatives = db.get_alternatives(sku, in_stock_only=True, channel=channel)
        product['alternatives'] = alternatives[:4]
        
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
def list_categories():
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM products")
        categories = [r[0] for r in cursor.fetchall()]
        conn.close()
        return categories
    except Exception as e:
        logger.error(f"Error listing categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files if compiled frontend/dist exists
from fastapi.staticfiles import StaticFiles
dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
    logger.info(f"Serving compiled frontend statically from: {dist_path}")
else:
    logger.info("Static frontend folder not found. Running in API-only mode.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
