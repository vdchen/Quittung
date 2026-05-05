import pytest
from unittest.mock import MagicMock, patch, mock_open
from app.tasks.worker import process_receipt_task
from app.services.notifications import format_receipt_error_ai_validation

@pytest.mark.asyncio
async def test_worker_with_malformed_ai_json(db_session):
    """
    Integration-style test: Mock the Gemini Client directly to return malformed data.
    This verifies that ai_service -> worker pipeline handles Pydantic validation errors.
    """
    file_path = "fake/receipt.jpg"
    chat_id = 111222
    
    # We patch the GenAI Client inside ai_service
    with patch("app.services.ai_service.genai.Client") as mock_client_class, \
         patch("builtins.open", mock_open(read_data=b"fake_bytes")), \
         patch("os.path.exists", return_value=True), \
         patch("app.tasks.worker.send_telegram_message") as mock_tg, \
         patch("app.tasks.worker.async_session_maker") as mock_session_factory, \
         patch("app.tasks.worker.current_task") as mock_task:

        # 1. Setup Worker/Session
        mock_session_factory.return_value.__aenter__.return_value = db_session
        mock_task.request.retries = 5
        mock_task.max_retries = 5

        # 2. Setup Gemini Mock to return invalid data
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        # Missing required 'total_amount' and 'currency'
        mock_response.parsed = {"merchant_name": "Broken Store"} 
        mock_client.models.generate_content.return_value = mock_response

        # 3. Execute Task
        # This will call process_receipt_image -> genai.Client -> ReceiptExtractionSchema.model_validate
        # model_validate will raise ValidationError
        result = await process_receipt_task(file_path, "image/jpeg", chat_id)

        # 4. Assertions
        assert result["status"] == "error"
        # The worker should have caught the ValidationError and eventually notified the user
        mock_tg.assert_called_with(
            chat_id,
            format_receipt_error_ai_validation()
        )

@pytest.mark.asyncio
async def test_worker_with_valid_ai_json(db_session):
    """
    Verify the successful integration path by mocking the Gemini Client.
    """
    file_path = "fake/receipt.jpg"
    chat_id = 333444
    
    with patch("app.services.ai_service.genai.Client") as mock_client_class, \
         patch("builtins.open", mock_open(read_data=b"fake_bytes")), \
         patch("os.path.exists", return_value=True), \
         patch("app.tasks.worker.send_telegram_message") as mock_tg, \
         patch("app.tasks.worker.async_session_maker") as mock_session_factory:

        mock_session_factory.return_value.__aenter__.return_value = db_session

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.parsed = {
            "merchant_name": "Real Integration Store",
            "total_amount": 42.50,
            "currency": "EUR",
            "items": [{"name": "Life", "price": 42.0, "category": "Other"}]
        }
        mock_client.models.generate_content.return_value = mock_response

        result = await process_receipt_task(file_path, "image/jpeg", chat_id)

        assert result["status"] == "success"
        mock_tg.assert_called()
        args, _ = mock_tg.call_args
        assert "Real Integration Store" in args[1]
        assert "42.5" in args[1]
