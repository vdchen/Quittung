import pytest
from pathlib import Path
from app.services.ai_service import process_receipt_image

# Path to test receipt
TEST_IMAGE_PATH = Path("/app/tests/sample_receipt.pdf")

@pytest.mark.asyncio
async def test_process_receipt_integration():
    """
    Integration test: Calls the actual Gemini API.
    Ensures the mapping from PDF -> Gemini -> Pydantic Schema is intact.
    """
    # 1. Setup: Ensure the file exists
    assert TEST_IMAGE_PATH.exists(), f"Test file not found at {TEST_IMAGE_PATH}"
    
    with open(TEST_IMAGE_PATH, "rb") as f:
        image_bytes = f.read()

    # 2. Execution
    result = await process_receipt_image(image_bytes, mime_type="application/pdf")

    # 3. Clinical Validation
    assert "REWE Markt" in result.merchant_name
    assert result.total_amount == 66.12
    assert result.currency == "EUR"
    assert len(result.items) > 0, "No line items were extracted"
    
    # Check a specific known item from your earlier successful run
    item_names = [item.name for item in result.items]
    assert "GRANA PADANO" in item_names
    
    # Validate data types (Pydantic does most of this, but we double-check logic)
    for item in result.items:
        assert item.price > 0
        assert isinstance(item.category, str)

@pytest.mark.asyncio
async def test_invalid_mime_type_raises_error():
    """Ensure the service handles unsupported files gracefully"""
    # Placeholder for negative testing
    pass