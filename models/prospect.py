from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .contact_info import ContactInfo


class Prospect(BaseModel):
    name: str = Field(..., description="Full name of the prospect")
    title: str | None = Field(None, description="Current role or title")
    company: str | None = Field(None, description="Current company")
    location: str | None = Field(None, description="Location")
    contact: ContactInfo | None = Field(None, description="Contact details")
