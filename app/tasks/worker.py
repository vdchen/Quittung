import asyncio
import httpx
import os
import logging
from app.config import settings
from app.core.celery_app import celery_app
from app.services.ai_service import process_receipt_image
from app.services.receipt_service import save_extracted_receipt
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

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
            # Telegram uses 'json' for simple messages, 
            # but 'data' for multipart (files)
            if files:
                response = await client.post(url, data=payload, files=files)
            else:
                response = await client.post(url, json=payload)
            
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Telegram API Error ({method}): {e}")

async def send_telegram_message(chat_id: int, text: str):
    """Public helper for text messages."""
    if not chat_id: return
    await _send_telegram_request("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

async def send_telegram_document(chat_id: int, file_path: str, caption: str = ""):
    """Public helper for documents."""
    if not chat_id or not os.path.exists(file_path): return
    
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    with open(file_path, "rb") as f:
        await _send_telegram_request("sendDocument", payload, files={"document": f})     

@celery_app.task(name="app.tasks.worker.process_receipt_task")
def process_receipt_task(file_path: str, mime_type: str, chat_id: int | None = None):
    async def run_process():
        try:
            # 1. Load File
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            async with async_session_maker() as db:
                # 2. AI Extraction
                extraction = await process_receipt_image(file_bytes, mime_type=mime_type)
                
                # 3. Save to DB (Passing telegram_id for multi-tenancy)
                receipt_obj = await save_extracted_receipt(
                    db=db, 
                    extraction=extraction, 
                    telegram_id=chat_id, 
                    image_url=file_path
                )
                
                # 4. Handle Duplicates
                if receipt_obj is None:
                    await send_telegram_message(
                        chat_id, 
                        "⚠️ <b>Duplicate Detected:</b> This receipt has already been processed."
                    )
                    return {"status": "duplicate"}

                # 5. Capture values before session closes
                receipt_id = receipt_obj.id
                merchant = extraction.merchant_name or "Unknown"
                date_str = extraction.date.strftime("%Y-%m-%d") if extraction.date else "N/A"
                total = extraction.total_amount or 0.00
                currency = extraction.currency or "€"

                # 6. Format Line Items 
                items_text = ""
                if extraction.items:
                    items_text = "<b>📦 Items:</b>\n"
                    for item in extraction.items:
                        if isinstance(item, dict):
                            name = item.get("name", "Unknown Item")
                            price = item.get("price", 0.00)
                            category = item.get("category", "Uncategorized")
                        else:
                            name = getattr(item, "name", "Unknown Item")
                            price = getattr(item, "price", 0.00)
                            category = getattr(item, "category", "Uncategorized")
                        
                        items_text += f" • {name} | {price} {currency} (<i>{category}</i>)\n"
                
                await db.commit()

            # 7. Success Notification
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
            raise e
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Test Environment: loop exists, schedule task
        return loop.create_task(run_process()) 
    else:
        # Production Environment: no loop exists, create one
        return asyncio.run(run_process())

@celery_app.task(name="app.tasks.worker.generate_export_task")
def generate_export_task(file_name: str, chat_id: int | None = None):
    async def run_export_and_notify():
        # Lazy import to prevent circular dependency
        from app.services.export_service import generate_expenses_report
        
        async with async_session_maker() as db:
            # Generate the report filtered by telegram_id
            output_path = await generate_expenses_report(db, telegram_id=chat_id, file_name=file_name)
            
            if output_path and chat_id:
                await send_telegram_document(
                    chat_id=chat_id, 
                    file_path=output_path, 
                    caption="Here is your spending report! 📊"
                )
            
            return {"status": "completed", "file_path": output_path}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return loop.create_task(run_export_and_notify()) 
    else:
        return asyncio.run(run_export_and_notify())