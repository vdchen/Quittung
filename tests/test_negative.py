import pytest
from unittest.mock import patch, mock_open, MagicMock
from app.tasks.worker import process_receipt_task
from app.services.ai_service import process_receipt_image
from app.services.notifications import format_receipt_error_protected
from pydantic import ValidationError

@pytest.mark.asyncio
async def test_process_receipt_encrypted_pdf(db_session):
    """
    Simulate processing an encrypted PDF. 
    Worker should recognize the 'password' keyword and notify the user specifically without retrying.
    """
    file_path = "tests/assets/encrypted.pdf"
    chat_id = 12345
    
    with patch("builtins.open", mock_open(read_data=b"%PDF-1.4 encrypted content")), \
         patch("os.path.exists", return_value=True), \
         patch("app.tasks.worker.process_receipt_image", side_effect=Exception("File is password protected")), \
         patch("app.tasks.worker.send_telegram_message") as mock_tg, \
         patch("app.tasks.worker.current_task") as mock_task:
        
        # We don't need to mock retries because it should skip them
        result = await process_receipt_task(file_path, "application/pdf", chat_id)
        
        assert result["status"] == "error"
        assert "password protected" in result["message"]
        
        # Verify user is notified with the SPECIFIC message
        mock_tg.assert_called_with(
            chat_id,
            format_receipt_error_protected()
        )
        
        # Verify it did NOT retry (raise current_task.retry)
        mock_task.retry.assert_not_called()

@pytest.mark.asyncio
async def test_process_receipt_corrupted_file(db_session):
    """
    Simulate a corrupted file that causes the AI service to raise an error.
    Worker should recognize 'format' and skip retries.
    """
    file_path = "tests/assets/corrupted.jpg"
    chat_id = 12345
    
    with patch("builtins.open", mock_open(read_data=b"not an image")), \
         patch("os.path.exists", return_value=True), \
         patch("app.tasks.worker.process_receipt_image", side_effect=Exception("Invalid image format")), \
         patch("app.tasks.worker.send_telegram_message") as mock_tg, \
         patch("app.tasks.worker.current_task") as mock_task:
        
        result = await process_receipt_task(file_path, "image/jpeg", chat_id)
        
        assert result["status"] == "error"
        assert "Invalid image format" in result["message"]
        mock_task.retry.assert_not_called()
        mock_tg.assert_called_with(chat_id, "❌ <b>Processing Failed:</b> Invalid image format")

@pytest.mark.asyncio
async def test_ai_service_validation_error(db_session):
    """
    Test when AI returns malformed JSON that fails Pydantic validation.
    """
    with patch("app.services.ai_service._get_genai_client") as mock_client_factory:
        mock_client = mock_client_factory.return_value
        # Mock Gemini returning something that isn't valid for our schema
        mock_response = MagicMock()
        mock_response.parsed = {"invalid": "data"} 
        mock_client.models.generate_content.return_value = mock_response
        
        # We expect a ValidationError from model_validate
        with pytest.raises(ValidationError):
            await process_receipt_image(b"fake_bytes", "image/jpeg")

@pytest.mark.asyncio
async def test_process_receipt_db_connection_error():
    """
    Test task behavior when the database is unavailable.
    """
    file_path = "tests/assets/receipt.jpg"
    chat_id = 555
    
    with patch("builtins.open", mock_open(read_data=b"fake_bytes")), \
         patch("os.path.exists", return_value=True), \
         patch("app.tasks.worker.process_receipt_image"), \
         patch("app.tasks.worker.async_session_maker", side_effect=Exception("DB Connection Refused")), \
         patch("app.tasks.worker.send_telegram_message") as mock_tg, \
         patch("app.tasks.worker.current_task") as mock_task:
        
        mock_task.request.retries = 5
        mock_task.max_retries = 5
        
        # This should be caught by the general exception handler in the task
        result = await process_receipt_task(file_path, "image/jpeg", chat_id)
        
        assert result["status"] == "error"
        assert "DB Connection Refused" in result["message"]
        mock_tg.assert_called()

@pytest.mark.asyncio
async def test_process_receipt_file_not_found(db_session):
    """
    Test behavior when the file path passed to the worker does not exist.
    """
    file_path = "non_existent.jpg"
    chat_id = 123
    
    with patch("os.path.exists", return_value=False), \
         patch("app.tasks.worker.send_telegram_message"):
        
        # FileNotFoundError will be caught by the general exception handler
        result = await process_receipt_task(file_path, "image/jpeg", chat_id)
        
        # Since we patched os.path.exists to False, the open() call will fail in reality 
        # but here the task fails at step 0 or during open
        assert result["status"] == "error"


@pytest.mark.asyncio
async def test_invalid_mime_type_raises_error():
    """
    Ensure the service handles unsupported files gracefully by raising a ValueError
    when a MIME type not in the supported list is provided.
    """
    from app.services.ai_service import process_receipt_image
    
    with pytest.raises(ValueError, match="Unsupported file format: text/plain"):
        await process_receipt_image(b"some text", mime_type="text/plain")

@pytest.mark.asyncio
async def test_ai_service_gemini_error():
    """
    Test how ai_service handles a direct exception from the Gemini SDK.
    """
    with patch("app.services.ai_service._get_genai_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        
        mock_client.models.generate_content.side_effect = Exception("Gemini API Error")
        
        with pytest.raises(Exception) as exc:
            await process_receipt_image(b"fake_bytes", "image/jpeg")
        
        assert "Gemini API Error" in str(exc.value)