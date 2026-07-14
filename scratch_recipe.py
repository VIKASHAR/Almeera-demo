import asyncio
import sys
import os
import json
sys.path.append(os.getcwd())
import src.database as db
from src.config import llm_call

prompt = """
Generate a simple recipe for: "sandwich".
Ensure this recipe strictly follows a low-fat diet.
Do NOT include any ingredients containing or derived from: nuts.

Keep the ingredient list small (5 items or less).
Respond STRICTLY in JSON format with the following keys:
- "dish_name": string
- "ingredients": list of strings
"""
system_instruction = "You are a recipe ingredient extractor. Output ONLY the JSON structure."
response_raw = llm_call(prompt, system_instruction=system_instruction, json_mode=True)
print("Raw Response:", response_raw)
recipe_data = json.loads(response_raw)
ingredients = recipe_data.get("ingredients", [])
print("Ingredients:", ingredients)
mapped_skus_dict = db.map_ingredients_to_skus(ingredients)
for ing, prod in mapped_skus_dict.items():
    print(f"Ingredient: {ing} -> Product: {prod['name'] if prod else None}")
