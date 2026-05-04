import asyncio
from google import genai
from google.genai import types
from app.schemas.receipt import ReceiptExtractionSchema
from app.core.config import settings


def _get_genai_client() -> genai.Client:
    """Return a configured Gemini client. Raises clearly if the key is missing."""
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not configured")
    return genai.Client(api_key=settings.GOOGLE_API_KEY)


async def process_receipt_image(
    file_bytes: bytes, mime_type: str = "image/jpeg"
) -> ReceiptExtractionSchema:
    """
    Send the receipt bytes to Gemini and return a structured extraction.

    The underlying SDK call is synchronous, so it is executed in a thread-pool
    executor to avoid blocking the async event loop.
    """
    if mime_type not in settings.SUPPORTED_MIME_TYPES:
        raise ValueError(f"Unsupported file format: {mime_type}")

    client = _get_genai_client()

    prompt = (
        "Task: Act as a specialized OCR and Data Extraction engine. "
        "Analyze the provided receipt and return a structured JSON object. "
        "Extraction Rules: "
        "Merchant: Extract the full legal name of the store. "
        "Date: Return in YYYY-MM-DD format. "
        "Total: Extract the final amount paid as a float. "
        "Currency: Extract the ISO currency code (e.g., EUR, USD, UAH). "
        "Categorized Items: For each line item, extract the name, price, "
        "and a single category from the following allowed list: "
        "[Bakery, Pantry, Meat, Vegetables, Fruits, Drinks, Snacks, Dairy, Household, Deposit, Other]. "
        "Specific Logic:"
        "If an item is 'Pfand' or a bottle return, it must be categorized as Deposit. "
        "Do not use hierarchical names like 'Groceries (Fruits)'; use only the specific category name (e.g., Fruits). "
        "If you are unsure of a category, use Other. "
        "Output Format: Strict JSON only."
    )

    def _call_gemini() -> ReceiptExtractionSchema:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReceiptExtractionSchema,
                temperature=0,
            ),
        )
        return ReceiptExtractionSchema.model_validate(response.parsed)

    # Run the blocking SDK call in the default thread-pool executor so it
    # does not stall the event loop while waiting for the Gemini response.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call_gemini)
