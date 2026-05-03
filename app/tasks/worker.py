import asyncio
import httpx
import os
import logging
import html
from app.core.config import settings
from app.core.celery_app import celery_app
from app.services.ai_service import process_receipt_image
from app.services.receipt_service import save_extracted_receipt
from app.services.export_service import generate_expenses_report
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker as _async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def async_session_maker():
    """
    Creates an isolated database engine and session for a single Celery task.
    Because Celery tasks run in isolated asyncio.run() loops, sharing a global 
    AsyncEngine across tasks causes fatal loop-attachment errors in asyncpg.
    """
    engine = create_async_engine(
        settings.DATABASE_URL, 
        poolclass=NullPool, 
        echo=settings.DEBUG, 
        future=True
    )
    maker = _async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _send_telegram_request(method: str, payload: dict, files: dict | None = None):
    """
    Internal generic helper to handle all Telegram API communication.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if files:
                response = await client.post(url, data=payload, files=files)
            else:
                response = await client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Telegram API Error ({method}): {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Telegram API Error ({method}): {e}")


async def send_telegram_message(chat_id: int, text: str):
    """Public helper for text messages."""
    if not chat_id:
        return
    await _send_telegram_request(
        "sendMessage",
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
    )


async def send_telegram_document(chat_id: int, file_path: str, caption: str = ""):
    """Public helper for documents."""
    if not chat_id or not os.path.exists(file_path):
        return
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    with open(file_path, "rb") as f:
        await _send_telegram_request("sendDocument", payload, files={"document": f})


@celery_app.task(name="app.tasks.worker.process_receipt_task")
def process_receipt_task(file_path: str, mime_type: str, chat_id: int | None = None):
    """
    Celery task that processes a receipt file end-to-end:
      1. Read file bytes from disk
      2. Call Gemini AI for structured extraction
      3. Persist receipt + line items to the database
      4. Notify the user via Telegram

    Async implementation detail
    ----------------------------
    Celery workers run in a synchronous context (no running event loop).
    In that case asyncio.run() creates a fresh loop, executes the coroutine
    to completion, and returns the result — the standard pattern.

    During tests pytest-asyncio provides a running loop, so we schedule the
    coroutine as a Task on it instead; the test then awaits that Task to get
    the actual return value.
    """
    async def _run():
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            async with async_session_maker() as db:
                # 1. AI Extraction
                extraction = await process_receipt_image(file_bytes, mime_type=mime_type)

                # 2. Persist to DB
                receipt_obj = await save_extracted_receipt(
                    db=db,
                    extraction=extraction,
                    telegram_id=chat_id,
                    file_path=file_path,
                )

                # 3. Duplicate guard
                if receipt_obj is None:
                    await send_telegram_message(
                        chat_id,
                        "⚠️ <b>Duplicate Detected:</b> This receipt has already been processed.",
                    )
                    return {"status": "duplicate"}

                # 4. Capture values before the session is closed
                receipt_id = receipt_obj.id
                merchant = html.escape(extraction.merchant_name or "Unknown")
                date_str = extraction.date.strftime("%Y-%m-%d") if extraction.date else "N/A"
                total = extraction.total_amount or 0.00
                currency = extraction.currency or "€"

                # 5. Format line items
                items_text = ""
                if extraction.items:
                    items_text = "<b>📦 Items:</b>\n"
                    for item in extraction.items:
                        if isinstance(item, dict):
                            name = html.escape(item.get("name", "Unknown Item"))
                            price = item.get("price", 0.00)
                            category = html.escape(item.get("category", "Uncategorized"))
                        else:
                            name = html.escape(getattr(item, "name", "Unknown Item"))
                            price = getattr(item, "price", 0.00)
                            category = html.escape(getattr(item, "category", "Uncategorized"))
                        items_text += f" • {name} | {price} {currency} (<i>{category}</i>)\n"

            # 6. Success notification (outside session — session is already committed)
            if chat_id:
                text = (
                    f"✅ <b>Receipt Processed</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📅 <b>Date:</b> {date_str}\n"
                    f"🏪 <b>Merchant:</b> {merchant}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{items_text}"
                    f"━━━━━━━━━━━━━━━\n"
                    f"💰 <b>Total Amount:</b> {total} {currency}\n"
                )
                await send_telegram_message(chat_id, text)

            return {"status": "success", "receipt_id": receipt_id}

        except Exception as e:
            logger.error(f"Task Failed: {str(e)}")
            if chat_id:
                await send_telegram_message(chat_id, "❌ <b>Error:</b> Processing failed.")
            raise

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Test context: a pytest-asyncio event loop is already running.
        # create_task schedules _run(); the test awaits the returned Task.
        return loop.create_task(_run())
    else:
        # Production context: Celery worker thread has no running loop.
        return asyncio.run(_run())


@celery_app.task(name="app.tasks.worker.generate_export_task")
def generate_export_task(file_name: str, chat_id: int | None = None):
    async def _run():
        async with async_session_maker() as db:
            output_path = await generate_expenses_report(
                db, telegram_id=chat_id, file_name=file_name
            )

            if output_path and chat_id:
                await send_telegram_document(
                    chat_id=chat_id,
                    file_path=output_path,
                    caption="Here is your spending report! 📊",
                )
            elif chat_id:
                await send_telegram_message(
                    chat_id=chat_id,
                    text="📭 <b>No receipts found.</b> You haven't uploaded any receipts yet!"
                )

            return {"status": "completed", "file_path": output_path}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return loop.create_task(_run())
    else:
        return asyncio.run(_run())