import os
from google import genai
from google.genai import types
from app.schemas.receipt import ReceiptExtractionSchema
from dotenv import load_dotenv

load_dotenv() 

# The SDK uses a Client class
def get_genai_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set")
    return genai.Client(api_key=api_key)


async def process_receipt_image(file_bytes: bytes, mime_type: str = "image/jpeg") -> ReceiptExtractionSchema:
    
    client = get_genai_client()

    prompt = "Task: Act as a specialized OCR and Data Extraction engine. " \
    "Analyze the provided receipt and return a structured JSON object. " \
    "Extraction Rules: " \
    "Merchant: Extract the full legal name of the store. " \
    "Date: Return in YYYY-MM-DD format. " \
    "Total: Extract the final amount paid as a float. " \
    "Currency: Extract the ISO currency code (e.g., EUR, USD, UAH). " \
    "Categorized Items: For each line item, extract the name, price, " \
    "and a single category from the following allowed list: " \
    "[Bakery, Pantry, Meat, Vegetables, Fruits, Drinks, Snacks, Dairy, Household, Deposit, Other]." \
    "Specific Logic:" \
    "If an item is 'Pfand' or a bottle return, it must be categorized as Deposit." \
    "Do not use hierarchical names like 'Groceries (Fruits)'; use only the specific category name (e.g., Fruits)." \
    "If you are unsure of a category, use Other." \
    "Output Format: Strict JSON only."


    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
                ]
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReceiptExtractionSchema,
            temperature=0,
        )
    )

    return ReceiptExtractionSchema.model_validate(response.parsed)
