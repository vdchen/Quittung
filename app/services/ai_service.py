import os
from google import genai
from google.genai import types
from app.schemas.receipt import ReceiptExtractionSchema
from dotenv import load_dotenv

load_dotenv()  # Ensure .env is loaded

# The new SDK uses a Client class
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


async def process_receipt_image(file_bytes: bytes, mime_type: str = "image/jpeg") -> ReceiptExtractionSchema:
    prompt = "Analyze this receipt. Extract the merchant name, date, total amount, currency, and categorized items. " \
    "If the category is Groceries, split it into subcategory like Meat, Vegtables, Fruits, Drinks, Snaks, etc. " \
    "If it is pfand, categorize it as a deposit."

    # The SDK wants a list of Parts or Strings.
    # For bytes, use this specific dictionary structure:
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
