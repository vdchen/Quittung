import pytest
import asyncio
from unittest.mock import patch
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.receipt import Receipt
from app.schemas.receipt import ReceiptExtractionSchema
from app.services.receipt_service import save_extracted_receipt
from tests.conftest import TestSessionLocal

@pytest.mark.asyncio
async def test_duplicate_check_race_condition():
    """
    Test that two workers processing the same receipt at the same time
    could potentially create duplicates if no database-level unique constraints exist.
    
    This test confirms the 'check-then-act' race condition in receipt_service.py.
    """
    extraction = ReceiptExtractionSchema(
        merchant_name="Race Condition Store",
        total_amount=99.99,
        currency="EUR",
        date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        items=[{"name": "Item 1", "price": 99.99, "category": "Test"}]
    )
    telegram_id = 999

    # We use two separate database sessions to simulate two different workers/processes
    async with TestSessionLocal() as session1:
        async with TestSessionLocal() as session2:
            
            # We want to force both sessions to perform the 'is_duplicate' check
            # BEFORE either one commits the new record.
            from app.services.receipt_service import is_duplicate
            
            original_is_duplicate = is_duplicate
            
            async def mocked_is_duplicate(*args, **kwargs):
                # Wait a bit to ensure both tasks reach this point and overlap
                await asyncio.sleep(0.3)
                return await original_is_duplicate(*args, **kwargs)

            with patch("app.services.receipt_service.is_duplicate", side_effect=mocked_is_duplicate):
                # Run both concurrently; we only care about the DB state afterwards
                await asyncio.gather(
                    save_extracted_receipt(session1, extraction, telegram_id),
                    save_extracted_receipt(session2, extraction, telegram_id),
                    return_exceptions=True
                )

            # In a ROBUST implementation, only ONE task should succeed in creating a record.
            # The other should either return the existing one or detect the duplicate.
            
            # Check the database - we should have EXACTLY 1 receipt
            async with TestSessionLocal() as session3:
                stmt = select(Receipt).where(
                    Receipt.telegram_id == telegram_id,
                    Receipt.merchant_name == "Race Condition Store"
                )
                result = await session3.execute(stmt)
                receipts = result.scalars().all()
                
            # DB-level UniqueConstraint (uq_receipt_duplicate) ensures that even when
            # two concurrent workers both pass the is_duplicate() check before either
            # commits, the database rejects the second INSERT — guaranteeing exactly
            # one receipt is stored regardless of timing.
            assert len(receipts) == 1, (
                f"Race condition not blocked! Expected 1 receipt, found {len(receipts)}."
            )
