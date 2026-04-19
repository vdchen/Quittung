from sqlalchemy.ext.asyncio import AsyncSession
from app.models.receipt import Receipt, LineItem
from app.schemas.receipt import ReceiptExtractionSchema # Pydantic model
from datetime import datetime, timezone
from dateutil import parser
import logging

logger = logging.getLogger(__name__)


async def save_extracted_receipt(
    db: AsyncSession, 
    extraction: ReceiptExtractionSchema, 
    image_url: str = None
) -> Receipt:
    """
    Orchestrates the creation of a Receipt and its associated LineItems.
    """
    try:
        # 1. Convert the AI string date to a Python datetime object
        # A "naive" datetime (no tzinfo) to match the DB
        valid_date = extraction.date or datetime.now(timezone.utc)


        # 2. Initialize the Receipt object
        
        new_receipt = Receipt(
            merchant_name=extraction.merchant_name,
            total_amount=extraction.total_amount,
            currency=extraction.currency,
            date=valid_date,
            image_url=image_url
        )

        db.add(new_receipt)
        
        # 2. Flush to generate the Receipt ID without committing yet
        # This is essential for the foreign key in LineItems
        await db.flush()

        # 3. Bulk create LineItems
        line_items = [
            LineItem(
                receipt_id=new_receipt.id,
                name=item.name,
                price=item.price,
                category=item.category
            )
            for item in extraction.items
        ]

        db.add_all(line_items)

        # 4. Atomic Commit
        await db.commit()
        
        # Refresh to load the relationships (items) back into the object
        await db.refresh(new_receipt, attribute_names=['items'])
        
        logger.info(f"Receipt from {new_receipt.merchant_name} saved with ID: {new_receipt.id}")
        return new_receipt

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save receipt: {str(e)}")
        raise e