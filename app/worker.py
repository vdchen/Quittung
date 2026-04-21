import asyncio
import httpx
import os
import logging
from app.core.celery_app import celery_app
from app.services.ai_service import process_receipt_image
from app.services.receipt_service import save_extracted_receipt
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

@celery_app.task(name="app.worker.process_receipt_task")
def process_receipt_task(file_path: str, mime_type: str):
    async def run_process():
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # Using a context manager that ensures a fresh session on this loop
            async with async_session_maker() as db:
                extraction = await process_receipt_image(file_bytes, mime_type=mime_type)
                
                receipt_obj = await save_extracted_receipt(db, extraction, image_url=file_path)
                
                # Critical: Access attributes before the session closes
                receipt_id = receipt_obj.id
                merchant = extraction.merchant_name
                total = extraction.total_amount
                
                await db.commit()
                
            logger.info(f"Task Complete: Processed {file_path}")
            
            return {
                "receipt_id": receipt_id,
                "merchant": merchant,
                "total": total
            }

        except Exception as e:
            logger.error(f"Task Failed for {file_path}: {str(e)}")
            raise e

    return asyncio.run(run_process())


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


@celery_app.task(name="app.worker.process_receipt_task")
def process_receipt_task(file_path: str, mime_type: str, chat_id: int | None = None):
    async def run_process():
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            async with async_session_maker() as db:
                extraction = await process_receipt_image(file_bytes, mime_type=mime_type)
                receipt_obj = await save_extracted_receipt(db, extraction, image_url=file_path)
                
                # Capture values before session closes
                receipt_id = receipt_obj.id
                merchant = extraction.merchant_name or "Unknown"
                date = extraction.date or "N/A"
                total = extraction.total_amount or 0.00
                currency = extraction.currency or "€"

                # Format Line Items
                items_text = ""
                if extraction.items:
                    items_text = "<b>📦 Items:</b>\n"
                    for item in extraction.items:
                        # Safety check: if item is Pydantic, use getattr. 
                        # If it's a dict, use .get()
                        if isinstance(item, dict):
                            name = item.get("name", "Unknown Item")
                            price = item.get("price", 0.00)
                            category = item.get("category", "Uncategorized")
                        else:
                            # This is what you need for your Pydantic objects:
                            name = getattr(item, "name", "Unknown Item")
                            price = getattr(item, "price", 0.00)
                            category = getattr(item, "category", "Uncategorized")
                            
                        items_text += f" • {name} | {price} {currency} (<i>{category}</i>)\n"
                        
                await db.commit()

            # --- Telegram Notification ---
            if TELEGRAM_BOT_TOKEN and chat_id:
                text = (
                    f"✅ <b>Receipt Processed</b>\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🆔 <b>ID:</b> <code>{receipt_id}</code>\n"
                    f"📅 <b>Date:</b> {date}\n"
                    f"🏪 <b>Merchant:</b> {merchant}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{items_text}"
                    f"━━━━━━━━━━━━━━━\n"
                    f"💰 <b>Total Amount:</b> {total} {currency}\n"
                )

                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

            return {"receipt_id": receipt_id, "merchant": merchant, "total": total}

        except Exception as e:
            logger.error(f"Task Failed: {str(e)}")
            if TELEGRAM_BOT_TOKEN and chat_id:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={"chat_id": chat_id, "text": "❌ <b>Error:</b> Could not process the receipt."})
            raise e

    return asyncio.run(run_process())


@celery_app.task(name="app.worker.generate_export_task")
def generate_export_task(file_name: str, chat_id: int | None = None):
    async def run_export_and_notify():
        async with async_session_maker() as db:
            from app.services.export_service import generate_expenses_report
            
            # 1. Generate the file
            output_path = await generate_expenses_report(db, file_name)
            
            # 2. Notify Telegram ONLY if a chat_id was provided
            if output_path and TELEGRAM_BOT_TOKEN and chat_id:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                async with httpx.AsyncClient() as client:
                    with open(output_path, "rb") as f:
                        await client.post(
                            url,
                            data={"chat_id": chat_id, "caption": "Here is your export! 📊"},
                            files={"document": f}
                        )
            
            return {"status": "completed", "file_path": output_path}

    return asyncio.run(run_export_and_notify())