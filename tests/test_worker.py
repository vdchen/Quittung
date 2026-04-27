import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock, mock_open
import httpx
from app.worker import process_receipt_task, generate_export_task, send_telegram_message
from app.schemas.receipt import ReceiptExtractionSchema, LineItemSchema
from app.models.receipt import Receipt    

@pytest.fixture
def mock_extraction_result():
    fixed_date = datetime(2026, 3, 9, 12, 0, 0)
    return ReceiptExtractionSchema(
        merchant_name="Worker Test Store",
        total_amount=100.0,
        currency="EUR",
        date=fixed_date,
        items=[LineItemSchema(name="Test Item", price=100.0, category="Test")]
    )

@pytest.mark.asyncio
async def test_process_receipt_task_success(db_session, mock_extraction_result):
    """
    Tests the full worker flow: File read -> AI Mock -> DB Save -> Telegram Mock.
    """
    file_path = "fake/path/receipt.jpg"
    chat_id = 99999
    
    # We must patch multiple things to isolate the worker
    with patch("builtins.open", mock_open(read_data=b"fake_bytes")), \
         patch("os.path.exists", return_value=True), \
         patch("app.worker.process_receipt_image") as mock_ai, \
         patch("app.worker.send_telegram_message") as mock_tg, \
         patch("app.worker.async_session_maker") as mock_session_factory:
        
        # 1. Setup Mocks
        mock_ai.return_value = mock_extraction_result
        # The worker creates its own session, so we make it use our test session
        mock_session_factory.return_value.__aenter__.return_value = db_session
        
        # 2. Execute Task
        # Note: We call the function directly, bypassing Celery's queue
        result = await process_receipt_task(file_path, "image/jpeg", chat_id)

        # Force the session to commit to the test database
        await db_session.commit()
        
        # 3. Clinical Assertions
        assert result["status"] == "success"
        
        # Verify DB entry was created
        receipt = (await db_session.execute(
            Receipt.__table__.select().where(Receipt.merchant_name == "Worker Test Store")
        )).first()
        assert receipt is not None
        
        # Verify Telegram was called with success message
        mock_tg.assert_called_once()
        args, _ = mock_tg.call_args
        assert "✅ <b>Receipt Processed</b>" in args[1]

@pytest.mark.asyncio
async def test_process_receipt_task_duplicate(db_session, mock_extraction_result):
    file_path = "fake/path/receipt.jpg"
    chat_id = 88888

    with patch("builtins.open", mock_open(read_data=b"fake_bytes")), \
         patch("os.path.exists", return_value=True), \
         patch("app.worker.process_receipt_image") as mock_ai, \
         patch("app.worker.send_telegram_message") as mock_tg, \
         patch("app.worker.async_session_maker") as mock_session_factory:

        mock_ai.return_value = mock_extraction_result
        mock_session_factory.return_value.__aenter__.return_value = db_session

        # First run
        await process_receipt_task(file_path, "image/jpeg", chat_id)
        
        # Ensure session is clear and data is persisted
        await db_session.commit()
        db_session.expire_all() 

        # Second run
        result = await process_receipt_task(file_path, "image/jpeg", chat_id)

        assert result["status"] == "duplicate"
        mock_tg.assert_called_with(chat_id, "⚠️ <b>Duplicate Detected:</b> This receipt has already been processed.")

@pytest.mark.asyncio
async def test_generate_export_task_success(db_session):
    chat_id = 285745690
    file_name = "test_report.xlsx"
    dummy_path = "uploads/test_report.xlsx"

    # Patch 'settings' inside app.worker
    with patch("app.worker.async_session_maker") as mock_session_factory, \
         patch("app.worker.settings") as mock_settings, \
         patch("app.services.export_service.generate_expenses_report") as mock_gen, \
         patch("app.worker.send_telegram_document", new_callable=AsyncMock) as mock_tg_doc:

        # Configure the mock settings
        mock_settings.TELEGRAM_BOT_TOKEN = "fake-token"
        
        mock_session_factory.return_value.__aenter__.return_value = db_session
        mock_gen.return_value = dummy_path

        result = await generate_export_task(file_name, chat_id)

        assert result["status"] == "completed"
        mock_tg_doc.assert_called_once()

@pytest.mark.asyncio
async def test_process_receipt_task_failure_notifies_telegram(db_session):
    with patch("app.worker.process_receipt_image", side_effect=Exception("AI Service Down")), \
         patch("app.worker.send_telegram_message") as mock_tg:
        
        # We expect the task to raise the exception after notifying Telegram
        with pytest.raises(Exception):
            await process_receipt_task("fake.jpg", "image/jpeg", chat_id=123)
        
        # Verify the error message was sent to the user
        mock_tg.assert_called_with(123, "❌ <b>Error:</b> Processing failed.")

@pytest.mark.asyncio
async def test_send_telegram_message_network_error():
    """Verify that network errors during Telegram sends are logged."""
    # Patch the settings object
    with patch("app.worker.settings") as mock_settings:
        mock_settings.TELEGRAM_BOT_TOKEN = "fake-token"
        
        with patch("app.worker.httpx.AsyncClient") as mock_client_class:
            mock_instance = mock_client_class.return_value.__aenter__.return_value
            mock_instance.post = AsyncMock(side_effect=httpx.RequestError("Connection Refused"))
            
            with patch("app.worker.logger") as mock_log:
                await send_telegram_message(12345, "Test message")

                mock_log.error.assert_called()
                args, _ = mock_log.error.call_args
                # Updated to match the new unified error string
                assert "Telegram API Error" in args[0]
                assert "Connection Refused" in args[0]