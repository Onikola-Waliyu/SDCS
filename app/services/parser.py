import json
import os
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an expert sales ledger assistant for market traders in Nigeria. 
Your task is to take a natural language message describing a sale and convert it into a structured JSON object.

Extract the following fields:
- item: The product sold (e.g., "rice", "beans", "eggs").
- quantity: The numeric quantity (e.g., 5, 2.5).
- unit: The unit of measure (e.g., "bags", "paint", "crates").
- amount: The total amount in Naira (convert 5k to 5000, 1m to 1000000).
- customer: The name of the customer, if mentioned.

Example Input: "I sold 5 bags of rice to Hilary for 200k"
Example Output: {"item": "rice", "quantity": 5, "unit": "bags", "amount": 200000, "customer": "Hilary"}

Example Input: "2 paint 10k each"
Example Output: {"item": "paint", "quantity": 2, "unit": "paint", "amount": 20000} (Note: 10k each * 2 = 20k)

If the message is not a sale, or you cannot understand it, return: {"error": "unsupported_format"}

Return ONLY the JSON object.
"""

def parse_sale_message(message: str) -> Optional[Dict[str, Any]]:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        if "error" in data:
            return None
        return data
    except Exception as e:
        print(f"Parsing error: {e}")
        return None
