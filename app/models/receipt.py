from sqlalchemy import BigInteger, Column, Integer, String, Float, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class Receipt(Base):
    __tablename__ = "receipts"

    __table_args__ = (
        UniqueConstraint(
            "telegram_id", "merchant_name", "total_amount", "date", 
            name="uq_receipt_duplicate"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, index=True)
    merchant_name = Column(String, nullable=True)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="EUR")
    date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="pending")  # pending, completed, failed
    # Renamed from image_url: this is a local filesystem path, not a URL.
    file_path = Column(String, nullable=True)

    # Relationship to individual items
    items = relationship("LineItem", back_populates="receipt",
                         cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String, nullable=True)

    receipt = relationship("Receipt", back_populates="items")
