from pydantic import BaseModel, Field
from typing import List, Optional


class LineItemSchema(BaseModel):
    name: str = Field(description="Exact name of the product or service")
    price: float = Field(
        description="Total price for this line item. Use 0.0 if not found.")
    category: str = Field(
        description="Categorize the item (e.g., Groceries, Transport, Electronics, Dining)")


class ReceiptExtractionSchema(BaseModel):
    merchant_name: Optional[str] = Field(
        description="Name of the store or merchant. Null if unreadable.")
    total_amount: float = Field(
        description="Total amount paid on the receipt.")
    currency: str = Field(
        description="3-letter currency code, e.g., EUR, USD, UAH. Default to EUR if unsure.")
    date: Optional[str] = Field(
        description="Date of purchase in YYYY-MM-DD format. Null if unreadable.")
    items: List[LineItemSchema] = Field(
        description="List of all purchased items.")
