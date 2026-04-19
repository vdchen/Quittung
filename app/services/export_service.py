import pandas as pd
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.receipt import Receipt

async def generate_expenses_report(db: AsyncSession, file_name: str = "report.xlsx") -> str:
    # 1. Fetch data with Line Items (Eager Loading)
    # We use selectinload to avoid the "N+1" query problem
    stmt = select(Receipt).options(selectinload(Receipt.items))
    result = await db.execute(stmt)
    receipts = result.scalars().all()
    
    if not receipts:
        return None

    # 2. Flatten data for Excel
    # Users usually want one row per line item
    flattened_data = []
    for r in receipts:
        for item in r.items:
            flattened_data.append({
                "Receipt ID": r.id,
                "Date": r.date.strftime("%Y-%m-%d") if r.date else "N/A",
                "Merchant": r.merchant_name,
                "Item Name": item.name,
                "Price": item.price,
                "Category": item.category,
                "Total Amount": r.total_amount,
                "Currency": r.currency
            })

    # 3. Handle Blocking I/O
    df = pd.DataFrame(flattened_data)
    output_path = f"uploads/{file_name}"
    
    # Run the heavy Pandas write operation in a thread pool
    # This prevents the async event loop from hanging
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, 
        lambda: df.to_excel(output_path, index=False, engine='openpyxl')
    )
    
    return output_path