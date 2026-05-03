import os
import uuid
import httpx
from fastapi import APIRouter, Request, Header, HTTPException
from aiogram import types, Bot, Dispatcher, F
from app.core.config import settings
from app.tasks.worker import process_receipt_task

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

# Dispatcher is stateless and safe to create at module level.
dp = Dispatcher()

UPLOAD_DIR = "uploads"


def _get_bot() -> Bot:
    """
    Lazily create the Bot instance so that a missing token raises a clear
    error at request time rather than crashing the application on startup.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Telegram bot is not configured (TELEGRAM_BOT_TOKEN missing).",
        )
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    """
    Endpoint for Telegram to POST updates to.

    Security: Telegram will include the secret token set via set_webhook()
    in the X-Telegram-Bot-Api-Secret-Token header on every request.
    Requests that omit or send the wrong token are rejected with 403.
    """
    # --- Webhook secret validation ---
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret.")

    bot = _get_bot()
    update_data = await request.json()
    update = types.Update(**update_data)
    await dp.feed_update(bot=bot, update=update)
    return {"status": "ok"}


@dp.message(F.document)
async def handle_webhook_document(message: types.Message):
    """Handle documents (e.g. PDF receipts) sent to the bot."""
    bot = _get_bot()
    doc = message.document
    file_info = await bot.get_file(doc.file_id)
    file_url = (
        f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}"
        f"/{file_info.file_path}"
    )

    ext = os.path.splitext(doc.file_name or "")[1] or ".bin"
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    async with httpx.AsyncClient() as client:
        resp = await client.get(file_url)
        if resp.status_code == 200:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(resp.content)
            process_receipt_task.delay(file_path, doc.mime_type, message.chat.id)
            await message.answer("✅ Processing your receipt now!")


@dp.message(F.photo)
async def handle_webhook_photo(message: types.Message):
    """Handle photo receipts sent to the bot."""
    bot = _get_bot()
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_url = (
        f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}"
        f"/{file_info.file_path}"
    )

    unique_filename = f"{uuid.uuid4()}.jpg"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    async with httpx.AsyncClient() as client:
        resp = await client.get(file_url)
        if resp.status_code == 200:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(resp.content)
            process_receipt_task.delay(file_path, "image/jpeg", message.chat.id)
            await message.answer("✅ Processing your receipt now!")