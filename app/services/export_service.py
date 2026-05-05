import uuid
import pandas as pd
import asyncio
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.receipt import Receipt
from app.core.config import settings

async def generate_expenses_report(
        db: AsyncSession, 
        telegram_id: int,
        file_name: str = None
        ) -> str:
    
    if file_name is None:
        file_name = f"report_{telegram_id}_{uuid.uuid4().hex[:8]}.xlsx"
        
    # 1. Fetch data with Line Items (Eager Loading)
														  
    stmt = (
        select(Receipt)
        .where(Receipt.telegram_id == telegram_id)
        .options(selectinload(Receipt.items))
    )
    result = await db.execute(stmt)
    receipts = result.scalars().all()
    
    if not receipts:
        return None

    # 2. Flatten data for Excel
											  
    flattened_data = []
    for r in receipts:
        for item in r.items:
            flattened_data.append({
                "Date": r.date.strftime("%Y-%m-%d") if r.date else "N/A",
                "Merchant": r.merchant_name,
                "Item Name": item.name,
                "Price": item.price,
                "Category": item.category,
                "Currency": r.currency
            })

    if not flattened_data:
        return None

    # 3. Data Processing
    df = pd.DataFrame(flattened_data)
    
    # Create a true datetime object column for reliable sorting and grouping
    df['Date_Obj'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Extract Month_Year (e.g., 'Jan_2026'). 'Unknown_Date' catches the "N/A" edge cases.
    df['Month_Year'] = df['Date_Obj'].dt.strftime('%b_%Y').fillna('Unknown_Date')

    # Global Category Summary
    global_summary_df = df.groupby("Category")["Price"].sum().reset_index()
    global_summary_df.columns = ["Category", "Total Spent"]

    output_path = os.path.join(settings.UPLOAD_DIR, file_name)
    
    def write_excel():
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Clean DataFrame for the global raw output (drop our internal sorting columns)
            clean_global_df = df.drop(columns=['Date_Obj', 'Month_Year'])
            
            # A. Global Raw Data Sheet
            clean_global_df.to_excel(writer, sheet_name="All Items", index=False)
            
            # B. Global Analytics Sheet
            global_summary_df.to_excel(writer, sheet_name="Global Analytics", index=False)

            # C. Monthly Sheets (Data + Analytics side-by-side)
            for month_year, group_df in df.groupby('Month_Year'):
                # Excel strictly limits sheet names to 31 characters
                safe_sheet_name = str(month_year)[:31]
                
                # Monthly Raw Data
                month_clean_df = group_df.drop(columns=['Date_Obj', 'Month_Year'])
                
                # Monthly Analytics
                month_summary = group_df.groupby("Category")["Price"].sum().reset_index()
                month_summary.columns = ["Category", "Total Spent"]

                # Write Raw Data starting at column A (default)
                month_clean_df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
                
                # Write Analytics on the same sheet, shifted right by (Number of Raw Columns + 2 empty buffer columns)
                start_col_for_analytics = len(month_clean_df.columns) + 2
                month_summary.to_excel(
                    writer, 
                    sheet_name=safe_sheet_name, 
                    startrow=0, 
                    startcol=start_col_for_analytics, 
                    index=False
                )

    # 4. Handle Blocking I/O
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, write_excel)
    
    return output_path