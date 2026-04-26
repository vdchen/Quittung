import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open
from app.worker import process_receipt_task, generate_export_task
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
    """
    Tests the export worker: DB Query -> File Generation -> Telegram Document Upload.
    """
    chat_id = 285745690
    file_name = "test_report.xlsx"
    dummy_path = "uploads/test_report.xlsx"

    # Patching dependencies
    with patch("app.worker.async_session_maker") as mock_session_factory, \
         patch("app.services.export_service.generate_expenses_report") as mock_gen, \
         patch("httpx.AsyncClient.post") as mock_post, \
         patch("builtins.open", mock_open(read_data=b"fake_excel_bytes")):
        
        # Setup Mocks
        mock_session_factory.return_value.__aenter__.return_value = db_session
        mock_gen.return_value = dummy_path
        
        # Execute Task (awaiting the returned task/coroutine)
        result = await generate_export_task(file_name, chat_id)

        # Assertions
        assert result["status"] == "completed"
        assert result["file_path"] == dummy_path
        mock_gen.assert_called_once()
        # Verify Telegram sendDocument was called
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert "sendDocument" in str(args[0])      

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
    """Covers lines 17-28: httpx Exception handling in worker."""
    from app.worker import send_telegram_message
    import httpx
    
    # Mock the post to raise an exception
    with patch("httpx.AsyncClient.post", side_effect=httpx.RequestError("Connection Refused")):
        with patch("app.worker.logger.error") as mock_log:
            await send_telegram_message(12345, "Test message")
            
            # Verify the error was logged
            mock_log.assert_called()
            assert "Failed to send Telegram notification" in mock_log.call_args[0][0]        