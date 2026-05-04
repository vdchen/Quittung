import pytest
from unittest.mock import AsyncMock, patch, MagicMock, mock_open
from app.core.config import settings
from tests.utils import get_url

@pytest.mark.asyncio
async def test_telegram_webhook_invalid_secret(client):
    """Verify that the webhook rejects requests with the wrong secret token."""
    with patch("app.api.endpoints.v1.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_WEBHOOK_SECRET = "super-secret"
        
        response = await client.post(
            get_url("/telegram/webhook"),
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"}
        )
        
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid webhook secret."

@pytest.mark.asyncio
async def test_telegram_webhook_success(client):
    """Verify that a valid webhook request feeds the update to the dispatcher."""
    with patch("app.api.endpoints.v1.telegram.settings") as mock_settings, \
         patch("app.api.endpoints.v1.telegram.dp.feed_update", new_callable=AsyncMock) as mock_feed:
        
        mock_settings.TELEGRAM_WEBHOOK_SECRET = "super-secret"
        mock_settings.TELEGRAM_BOT_TOKEN = "fake:token"
        
        # Mocking the Bot creation inside telegram_webhook
        with patch("app.api.endpoints.v1.telegram.Bot"):
            response = await client.post(
                get_url("/telegram/webhook"),
                json={"update_id": 123},
                headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret"}
            )
            
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            mock_feed.assert_called_once()

@pytest.mark.asyncio
async def test_command_start(client):
    """Test the /start command handler."""
    from aiogram import types
    from app.api.endpoints.v1.telegram import command_start_handler
    
    # Mocking a message
    message = AsyncMock(spec=types.Message)
    # Manually setup nested attributes for spec'd mock
    message.from_user = MagicMock()
    message.from_user.full_name = "Test User"
    message.answer = AsyncMock()
    
    await command_start_handler(message)
    
    message.answer.assert_called_once()
    args, _ = message.answer.call_args
    assert "Hi Test User!" in args[0]

@pytest.mark.asyncio
async def test_command_export(client):
    """Test the /export command handler triggers the celery task."""
    from aiogram import types
    from app.api.endpoints.v1.telegram import command_export_handler
    
    message = AsyncMock(spec=types.Message)
    message.chat = MagicMock()
    message.chat.id = 999
    message.answer = AsyncMock()
    
    with patch("app.api.endpoints.v1.telegram.generate_export_task.delay") as mock_task:
        await command_export_handler(message)
        
        # Using unittest.mock.ANY for the uuid-based filename
        from unittest.mock import ANY
        mock_task.assert_called_once_with(ANY, 999)
        message.answer.assert_called_once_with("⏳ Generating your Excel report... Please wait a moment.")

@pytest.mark.asyncio
async def test_handle_webhook_photo(client):
    """Test photo upload handler."""
    from aiogram import types
    from app.api.endpoints.v1.telegram import handle_webhook_photo
    
    message = AsyncMock(spec=types.Message)
    message.chat = MagicMock()
    message.chat.id = 123
    # Mock photo (list of PhotoSize, we take the last one)
    photo_mock = MagicMock(spec=types.PhotoSize)
    photo_mock.file_id = "photo_id"
    message.photo = [photo_mock]
    message.answer = AsyncMock()
    
    # Mock Bot and httpx
    mock_bot = AsyncMock()
    mock_bot.get_file.return_value = MagicMock(file_path="photos/file.jpg")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake-photo-binary"
    
    with patch("app.api.endpoints.v1.telegram._get_bot", return_value=mock_bot), \
         patch("httpx.AsyncClient.get", return_value=mock_resp), \
         patch("builtins.open", mock_open()), \
         patch("os.makedirs"), \
         patch("app.api.endpoints.v1.telegram.process_receipt_task.delay") as mock_task:
        
        await handle_webhook_photo(message)
        
        mock_task.assert_called_once()
        message.answer.assert_called_once_with("✅ Processing your receipt now!")

@pytest.mark.asyncio
async def test_handle_webhook_document(client):
    """Test document (PDF) upload handler."""
    from aiogram import types
    from app.api.endpoints.v1.telegram import handle_webhook_document
    
    message = AsyncMock(spec=types.Message)
    message.chat = MagicMock()
    message.chat.id = 456
    doc_mock = MagicMock(spec=types.Document)
    doc_mock.file_id = "doc_id"
    doc_mock.file_name = "receipt.pdf"
    doc_mock.mime_type = "application/pdf"
    message.document = doc_mock
    message.answer = AsyncMock()
    
    mock_bot = AsyncMock()
    mock_bot.get_file.return_value = MagicMock(file_path="docs/file.pdf")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake-pdf-binary"
    
    with patch("app.api.endpoints.v1.telegram._get_bot", return_value=mock_bot), \
         patch("httpx.AsyncClient.get", return_value=mock_resp), \
         patch("builtins.open", mock_open()), \
         patch("os.makedirs"), \
         patch("app.api.endpoints.v1.telegram.process_receipt_task.delay") as mock_task:
        
        await handle_webhook_document(message)
        
        from unittest.mock import ANY
        mock_task.assert_called_once_with(ANY, "application/pdf", 456)
        message.answer.assert_called_once_with("✅ Processing your receipt now!")

@pytest.mark.asyncio
async def test_get_bot_missing_token():
    """Verify that _get_bot raises HTTPException when token is missing."""
    from app.api.endpoints.v1.telegram import _get_bot
    from fastapi import HTTPException
    
    with patch("app.api.endpoints.v1.telegram.settings") as mock_settings:
        mock_settings.TELEGRAM_BOT_TOKEN = None
        with pytest.raises(HTTPException) as exc:
            _get_bot()
        assert exc.value.status_code == 503
        assert "TELEGRAM_BOT_TOKEN missing" in exc.value.detail
