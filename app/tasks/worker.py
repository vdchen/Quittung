import asyncio
from celery import current_task
from celery.exceptions import Retry
import httpx
import os
from app.core.config import settings
from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.services.ai_service import process_receipt_image
from app.services.receipt_service import save_extracted_receipt
from app.services.export_service import generate_expenses_report
from app.services.notifications import (
    format_receipt_success,
    format_receipt_duplicate,
    format_receipt_error_protected,
    format_receipt_error_generic,
    format_receipt_error_ai_validation,
    format_receipt_error_ai_unavailable,
    format_export_error,
    format_export_empty,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker as _async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager

logger = get_logger(__name__)


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
        logger.warning("telegram_skipped", reason="TELEGRAM_BOT_TOKEN not set")
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
            logger.error(
                "telegram_api_error",
                method=method,
                status_code=e.response.status_code,
                body=e.response.text,
            )
        except Exception as e:
            logger.error("telegram_request_failed", method=method, error=str(e))


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


@celery_app.task(
    name="app.tasks.worker.process_receipt_task",
    max_retries=5,
    retry_backoff=True,
    retry_jitter=True,
)
def process_receipt_task(file_path: str, mime_type: str, chat_id: int | None = None):
    """
    Celery task that processes a receipt file end-to-end with retries for transient failures.
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
                        chat_id, format_receipt_duplicate()
                    )
                    return {"status": "duplicate"}

            # 4. Success notification (outside session — session is already committed)
            if chat_id:
                await send_telegram_message(chat_id, format_receipt_success(extraction))

            logger.info(
                "receipt_processed",
                receipt_id=receipt_obj.id,
                merchant=receipt_obj.merchant_name,
                chat_id=chat_id,
            )
            return {"status": "success", "id": receipt_obj.id}

        except Retry:
            raise
        except Exception as e:
            from pydantic import ValidationError
            error_msg = str(e).lower()
            is_client_error = (
                any(kw in error_msg for kw in ["password", "encrypted", "protected", "invalid image"])
                or "unsupported file format" in error_msg
            )

            retries = current_task.request.retries if current_task and current_task.request else 0
            max_retries = current_task.max_retries if current_task else 5

            logger.error(
                "receipt_task_failed",
                attempt=retries,
                max_retries=max_retries,
                error=str(e),
                chat_id=chat_id,
            )

            # If it's a client error (encrypted, bad format), don't retry
            if is_client_error:
                if chat_id:
                    if "password" in error_msg or "encrypted" in error_msg:
                        msg = format_receipt_error_protected()
                    else:
                        msg = format_receipt_error_generic(str(e))
                    await send_telegram_message(chat_id, msg)
                return {"status": "error", "message": str(e)}

            # Handle Pydantic Validation Errors (Invalid AI response)
            if isinstance(e, ValidationError):
                logger.warning("ai_validation_error", error=str(e))
                if chat_id and retries >= max_retries:
                    await send_telegram_message(chat_id, format_receipt_error_ai_validation())
                if current_task and retries < max_retries:
                    raise current_task.retry(exc=e)
                return {"status": "error", "message": "AI validation failed"}

            # If we haven't reached max retries, trigger a retry
            if current_task and retries < max_retries:
                raise current_task.retry(exc=e)

            # Max retries reached — notify user
            if chat_id:
                await send_telegram_message(chat_id, format_receipt_error_ai_unavailable())
            return {"status": "error", "message": str(e)}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Test context: a pytest-asyncio event loop is already running.
        return loop.create_task(_run())
    else:
        # Production context: Celery worker thread has no running loop.
        return asyncio.run(_run())


@celery_app.task(
    name="app.tasks.worker.generate_export_task",
    max_retries=3,
    retry_backoff=True,
)
def generate_export_task(file_name: str, chat_id: int | None = None):
    """
    Task to generate an Excel report with retries for transient DB/IO failures.
    """
    async def _run():
        try:
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
                    await send_telegram_message(chat_id=chat_id, text=format_export_empty())

                logger.info("export_completed", file_name=file_name, chat_id=chat_id)
                return {"status": "completed", "file_path": output_path}

        except Retry:
            raise
        except Exception as e:
            retries = current_task.request.retries if current_task and current_task.request else 0
            max_retries = current_task.max_retries if current_task else 3

            logger.error(
                "export_task_failed",
                attempt=retries,
                max_retries=max_retries,
                error=str(e),
                chat_id=chat_id,
            )
            if current_task and retries < max_retries:
                raise current_task.retry(exc=e)

            if chat_id:
                await send_telegram_message(chat_id, format_export_error())
            return {"status": "error", "message": str(e)}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return loop.create_task(_run())
    else:
        return asyncio.run(_run())


@celery_app.task(name="app.tasks.worker.cleanup_uploads_task")
def cleanup_uploads_task():
    """
    Periodic task to delete files from the uploads directory that are older
    than settings.UPLOAD_CLEANUP_HOURS (default: 24h).
    """
    import time

    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        return {"status": "skipped", "reason": "directory not found"}

    now = time.time()
    cutoff = now - (settings.UPLOAD_CLEANUP_HOURS * 3600)
    deleted_count = 0

    for filename in os.listdir(upload_dir):
        file_path = os.path.join(upload_dir, filename)
        if os.path.isfile(file_path):
            file_mtime = os.path.getmtime(file_path)
            if file_mtime < cutoff:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info("upload_deleted", filename=filename)
                except Exception as e:
                    logger.error("upload_delete_failed", filename=filename, error=str(e))

    logger.info("cleanup_completed", deleted_count=deleted_count)
    return {"status": "success", "deleted_count": deleted_count}