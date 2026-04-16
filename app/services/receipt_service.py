from sqlalchemy.ext.asyncio import AsyncSession
from app.models.receipt import Receipt, LineItem
from app.schemas.receipt import ReceiptExtractionSchema # Pydantic model

async def save_receipt(db: AsyncSession, data: ReceiptExtractionSchema, image_url: str = None):
    # 1. Create the parent Receipt
    new_receipt = Receipt(
        store_name=data.merchant_name,
        total_amount=data.total_amount,
        currency=data.currency,
        date=data.date,
        image_url=image_url
    )
    
    db.add(new_receipt)
    await db.flush()  # Gets the ID without committing the whole transaction

    # 2. Map items to the Receipt
    for item in data.items:
        new_item = LineItem(
            receipt_id=new_receipt.id,
            name=item.name,
            price=item.price,
            category=item.category
        )
        db.add(new_item)

    await db.commit()
    await db.refresh(new_receipt)
    return new_receipt