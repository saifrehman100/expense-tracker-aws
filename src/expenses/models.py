"""Expense data models."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ExpenseUpdate(BaseModel):
    """Expense update request model."""

    amount: Optional[float] = Field(None, description="Expense amount")
    merchant: Optional[str] = Field(None, description="Merchant name")
    category: Optional[str] = Field(None, description="Expense category")
    date: Optional[str] = Field(None, description="Expense date (YYYY-MM-DD)")
    notes: Optional[str] = Field(None, description="Optional notes")


class Expense(BaseModel):
    """Expense model."""

    user_id: str
    expense_id: str
    amount: float
    merchant: str
    category: str
    date: str
    receipt_id: Optional[str] = None
    receipt_url: Optional[str] = None
    items: List[Dict[str, Any]] = []
    notes: Optional[str] = None
    raw_text: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: str
    updated_at: str

    class Config:
        """Pydantic config."""
        from_attributes = True


class ExpenseSummary(BaseModel):
    """Expense summary model."""

    total_amount: float
    expense_count: int
    by_category: Dict[str, float]
    by_month: Dict[str, float]
    average_expense: float
