from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datetime import datetime


class CreditUsage(BaseModel):
    """Credit usage information."""

    credits_used: int = Field(..., description="Number of credits used")
    timestamp: datetime = Field(..., description="When credits were used")
    operation_type: str = Field(..., description="Type of operation that used credits")


class CreditBalance(BaseModel):
    """Current credit balance information."""

    available_credits: int = Field(..., description="Available credits")
    total_credits: int = Field(..., description="Total credits in plan")
    usage_this_month: int = Field(..., description="Credits used this month")
    reset_date: datetime | None = Field(None, description="When credits reset")
