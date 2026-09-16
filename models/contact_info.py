from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class ContactInfo(BaseModel):
    email: EmailStr | None = Field(None, description="Primary email address")
    phone: str | None = Field(None, description="Primary phone number")
    linkedin: HttpUrl | None = Field(None, description="LinkedIn profile URL")
