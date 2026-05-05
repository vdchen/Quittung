"""
app/services/notifications.py
------------------------------
Centralised notification message formatters.

Keeping presentation logic (HTML templates, emoji, formatting) here means:
  - The worker stays focused on orchestration.
  - Adding a new channel (Slack, email) requires zero changes to worker.py.
  - Messages can be unit-tested without any Celery/DB context.
"""

import html
from app.schemas.receipt import ReceiptExtractionSchema


def format_receipt_success(extraction: ReceiptExtractionSchema) -> str:
    """
    Build the HTML notification sent to the user after a receipt is
    successfully processed.
    """
    merchant = html.escape(extraction.merchant_name or "Unknown")
    date_str = extraction.date.strftime("%Y-%m-%d") if extraction.date else "N/A"
    total = extraction.total_amount or 0.00
    currency = extraction.currency or "€"

    items_text = ""
    if extraction.items:
        items_text = "<b>📦 Items:</b>\n"
        for item in extraction.items:
            name = html.escape(
                item.get("name", "Item") if isinstance(item, dict)
                else getattr(item, "name", "Item")
            )
            price = (
                item.get("price", 0.0) if isinstance(item, dict)
                else getattr(item, "price", 0.0)
            )
            items_text += f" • {name} | {price} {currency}\n"

    return (
        f"✅ <b>Receipt Processed</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {date_str}\n"
        f"🏪 <b>Merchant:</b> {merchant}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{items_text}"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Total Amount:</b> {total} {currency}"
    )


def format_receipt_duplicate() -> str:
    """Notification sent when a duplicate receipt is detected."""
    return "⚠️ <b>Duplicate Detected:</b> This receipt has already been processed."


def format_receipt_error_protected() -> str:
    """Notification sent when an encrypted/password-protected file is submitted."""
    return (
        "❌ <b>Processing Failed:</b> This PDF is password protected and cannot be "
        "processed. Please upload an unencrypted version."
    )


def format_receipt_error_generic(message: str) -> str:
    """Notification sent for unrecoverable client-side errors."""
    return f"❌ <b>Processing Failed:</b> {message}"


def format_receipt_error_ai_validation() -> str:
    """Notification sent when the AI returns data that repeatedly fails validation."""
    return (
        "❌ <b>Processing Failed:</b> The AI service returned an invalid response. "
        "We tried to recover but failed. Please try again with a clearer image."
    )


def format_receipt_error_ai_unavailable() -> str:
    """Notification sent when the AI service is unreachable after all retries."""
    return (
        "❌ <b>Processing Failed:</b> We tried several times but the AI service is "
        "currently unavailable. Please try again later."
    )


def format_export_error() -> str:
    """Notification sent when the export task fails after all retries."""
    return (
        "❌ <b>Export Failed:</b> Something went wrong while generating your report. "
        "Please try again later."
    )


def format_export_empty() -> str:
    """Notification sent when there are no receipts to export."""
    return "📭 <b>No receipts found.</b> You haven't uploaded any receipts yet!"
