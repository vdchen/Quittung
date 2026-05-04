from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.receipt import Receipt, LineItem
from app.schemas.receipt import ReceiptExtractionSchema
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


async def save_extracted_receipt(
    db: AsyncSession,
    extraction: ReceiptExtractionSchema,
    telegram_id: int,
    file_path: str = None,
) -> Receipt:
    """
    Orchestrates the creation of a Receipt and its associated LineItems.
    Returns None if the receipt is a duplicate (same merchant, amount, date).
    """
    if await is_duplicate(db, telegram_id, extraction):
        logger.info(f"Duplicate receipt detected for user {telegram_id}. Skipping.")
        return None

    try:
        valid_date = extraction.date or datetime.now(timezone.utc)

        new_receipt = Receipt(
            telegram_id=telegram_id,
            merchant_name=extraction.merchant_name,
            total_amount=extraction.total_amount,
            currency=extraction.currency,
            date=valid_date,
            file_path=file_path,
            status="completed",
        )

        db.add(new_receipt)

        # Flush to get the Receipt PK before creating LineItems (FK dependency).
        await db.flush()

        line_items = [
            LineItem(
                receipt_id=new_receipt.id,
                name=item.name,
                price=item.price,
                category=item.category,
            )
            for item in extraction.items
        ]

        db.add_all(line_items)
        await db.commit()

        # Refresh to load the relationship back into the object.
        await db.refresh(new_receipt, attribute_names=["items"])

        logger.info(
            f"Receipt from {new_receipt.merchant_name} saved with ID: {new_receipt.id}"
        )
        return new_receipt

    except Exception as e:
        await db.rollback()
        
        # Handle race condition where two workers try to insert the same receipt at once
        # causing a UniqueConstraint violation in the database.
        error_msg = str(e).lower()
        if "unique" in error_msg or "duplicate" in error_msg:
            logger.info(f"Duplicate receipt blocked by DB constraint for user {telegram_id}.")
            return None
            
        logger.error(f"Failed to save receipt: {str(e)}")
        raise


async def is_duplicate(
    db: AsyncSession, telegram_id: int, extraction: ReceiptExtractionSchema
) -> bool:
    stmt = select(Receipt).where(
        Receipt.telegram_id == telegram_id,
        Receipt.merchant_name == extraction.merchant_name,
        Receipt.total_amount == extraction.total_amount,
        Receipt.date == extraction.date,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None