import os
import uuid
import httpx
import aiofiles
from fastapi import APIRouter, Request, Header, HTTPException
from aiogram import types, Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from app.core.config import settings
from app.tasks.worker import process_receipt_task, generate_export_task

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

# Dispatcher is stateless and safe to create at module level.
dp = Dispatcher()


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

    Security: Telegram includes the secret token (set via set_webhook()) in the
    X-Telegram-Bot-Api-Secret-Token header on every request.

    Validation is ALWAYS performed. If TELEGRAM_WEBHOOK_SECRET is not configured
    the server returns 500 (misconfiguration) rather than silently accepting all
    traffic.
    """
    # --- Webhook secret validation (unconditional) ---
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: TELEGRAM_WEBHOOK_SECRET is not set.",
        )
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret.")

    bot = _get_bot()
    update_data = await request.json()
    update = types.Update(**update_data)
    await dp.feed_update(bot=bot, update=update)
    return {"status": "ok"}


@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    """Handle /start command."""
    await message.answer(
        f"Hi {message.from_user.full_name}! 👋\n\n"
        "I am Quittung Bot. Send me a photo or a PDF of your receipt, "
        "and I will help you process it!\n\n"
        "📊 *Commands*:\n"
        "• /export - Get an Excel report of all your receipts.\n"
        "• /help - Shows help message.\n\n"
    )


@dp.message(Command("help"))
async def command_help_handler(message: types.Message):
    """Handle /help command."""
    await message.answer(
        "📖 *Quittung Bot Help*\n\n"
        "You can send me:\n"
        "1. 📄 *PDF Files* - PDF receipts will be parsed.\n"
        "2. 📸 *Photos* - Image receipts will be processed using OCR.\n\n"
        "📊 *Commands*:\n"
        "• /start - Shows start message.\n"
        "• /export - Get an Excel report of all your receipts.\n"
        "• /help - Shows help message.\n\n"
        "Just upload a file or use a command!",
        parse_mode="Markdown"
    )


@dp.message(Command("export"))
async def command_export_handler(message: types.Message):
    """Handle /export command."""
    # Use a shorter filename for the task
    file_name = f"report_{uuid.uuid4().hex[:8]}.xlsx"
    generate_export_task.delay(file_name, message.chat.id)
    await message.answer("⏳ Generating your Excel report... Please wait a moment.")


@dp.message(F.document)
async def handle_webhook_document(message: types.Message):
    """Handle documents (e.g. PDF receipts) sent to the bot."""
    bot = _get_bot()
    doc = message.document
    file_info = await bot.get_file(doc.file_id)
    # Build the Telegram file URL without exposing the token in logs/exceptions.
    # httpx does not include the URL body in RequestError messages, but keeping
    # the token out of the path string is an additional defence-in-depth measure.
    file_url = (
        f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}"
        f"/{file_info.file_path}"
    )

    ext = os.path.splitext(doc.file_name or "")[1] or ".bin"
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    async with httpx.AsyncClient() as client:
        resp = await client.get(file_url)
        if resp.status_code == 200:
            # Use aiofiles for non-blocking disk writes
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(resp.content)
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
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    async with httpx.AsyncClient() as client:
        resp = await client.get(file_url)
        if resp.status_code == 200:
            # Use aiofiles for non-blocking disk writes
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(resp.content)
            process_receipt_task.delay(file_path, "image/jpeg", message.chat.id)
            await message.answer("✅ Processing your receipt now!")