import pytest
import os
from unittest.mock import patch, MagicMock
from app.services.receipt_service import save_extracted_receipt, is_duplicate
from app.schemas.receipt import ReceiptExtractionSchema, LineItemSchema
from datetime import datetime
from app.services.export_service import generate_expenses_report
from app.models.receipt import Receipt

@pytest.fixture
def mock_extraction():
    """Returns a fake AI extraction object."""
    return ReceiptExtractionSchema(
        merchant_name="Test Store",
        total_amount=50.0,
        currency="EUR",
        date=datetime(2026, 1, 1),
        items=[
            LineItemSchema(name="Item 1", price=20.0, category="Food"),
            LineItemSchema(name="Item 2", price=30.0, category="Drinks")
        ]
    )

@pytest.mark.asyncio
async def test_save_extracted_receipt_success(db_session, mock_extraction):
    # Execute the service logic
    receipt = await save_extracted_receipt(
        db=db_session, 
        extraction=mock_extraction, 
        telegram_id=12345
    )

    assert receipt.id is not None
    assert receipt.merchant_name == "Test Store"
    assert len(receipt.items) == 2
    assert receipt.items[0].name == "Item 1"

@pytest.mark.asyncio
async def test_duplicate_detection(db_session, mock_extraction):
    # Save once
    await save_extracted_receipt(db_session, mock_extraction, telegram_id=12345)
    
    # Check for duplicate
    duplicate = await is_duplicate(db_session, 12345, mock_extraction)
    assert duplicate is True

@pytest.mark.asyncio
async def test_ai_service_mocking():
    """Example of how to mock the Gemini API call itself."""
    fake_data = {"merchant_name": "Mocked Shop", "total_amount": 10.50, "items": []}
    
    with patch("app.services.ai_service.process_receipt_image") as mocked_ai:
        # Configure the mock to return a MagicMock that behaves like your Pydantic model
        mocked_ai.return_value = MagicMock(spec=ReceiptExtractionSchema, **fake_data)
        
        # Now call your task or service that triggers the AI
        # result = await your_service_call()
        # assert result.merchant_name == "Mocked Shop"
        pass

@pytest.mark.asyncio
async def test_generate_expenses_report_creation(db_session):
    """
    Tests the actual creation of an Excel file by the service.
    """
    # 1. Seed the test database
    new_receipt = Receipt(
        telegram_id=12345,
        merchant_name="Test Shop",
        total_amount=50.0,
        currency="EUR"
    )
    db_session.add(new_receipt)
    await db_session.commit()

    # 2. Run service
    file_name = "test_export.xlsx"
    output_path = await generate_expenses_report(db_session, telegram_id=12345, file_name=file_name)

    # 3. Assertions
    assert output_path is not None
    assert os.path.exists(output_path)
    assert output_path.endswith(".xlsx")

    # Cleanup
    if os.path.exists(output_path):
        os.remove(output_path)