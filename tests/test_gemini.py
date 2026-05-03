import asyncio
import pytest
from app.services.ai_service import process_receipt_image


@pytest.mark.asyncio
async def test_extraction():
    # Path to test receipt
    image_path = "/app/tests/sample_receipt.pdf"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    print("Sending to Gemini...")
    result = await process_receipt_image(image_bytes, mime_type="application/pdf")

    print("\n EXTRACTION SUCCESSFUL:")
    print(f"Store: {result.merchant_name}")
    print(f"Total: {result.total_amount} {result.currency}")
    print(f"Items found: {len(result.items)}")
    for item in result.items:
        print(f" - {item.name}: {item.price} ({item.category})")

if __name__ == "__main__":
    asyncio.run(test_extraction())
