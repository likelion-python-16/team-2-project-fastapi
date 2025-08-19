# app/schemas/finance.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount: int
    payment_type: str          # "fee" | "deposit" 등
    status: str                # "paid" | "pending" | ...
    created_at: datetime

class PaymentListOut(BaseModel):
    items: list[PaymentOut]
    total: int
    skip: int
    limit: int

class SpendSummaryOut(BaseModel):
    total_paid: int
    total_refunded: int
    net_spent: int

