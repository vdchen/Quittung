import asyncio
import pytest
import logging
from app.services.ai_service import process_receipt_image

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_extraction():
    # Path to test receipt
    image_path = "/app/tests/sample_receipt.pdf"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    logger.info("Sending to Gemini...")
    result = await process_receipt_image(image_bytes, mime_type="application/pdf")

    logger.info("EXTRACTION SUCCESSFUL:")
    logger.info(f"Store: {result.merchant_name}")
    logger.info(f"Total: {result.total_amount} {result.currency}")
    logger.info(f"Items found: {len(result.items)}")
    for item in result.items:
        logger.info(f" - {item.name}: {item.price} ({item.category})")

if __name__ == "__main__":
    asyncio.run(test_extraction())
