from __future__ import annotations

try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Fallback for pydantic 1.x
    from pydantic import BaseModel, Field
    from pydantic import validator as field_validator


class SearchCriteria(BaseModel):
    title: str | None = Field(None, description="Job title or role to search for")
    location: str | None = Field(None, description="Location filter")
    company: str | None = Field(None, description="Company filter")
    industry: str | None = Field(None, description="Industry category")
    keywords: str | None = Field(None, description="Skills and attributes")
    name: str | None = Field(None, description="Full name to search for")
    experience_from: int | None = Field(None, description="Minimum years of experience")
    experience_to: int | None = Field(None, description="Maximum years of experience")
    open_to_work: bool | None = Field(None, description="Filter for job seekers only")
    size: int = Field(10, ge=1, le=5000, description="Max prospects to collect")
    scroll_id: str | None = Field(None, description="Scroll ID for pagination")
    continue_search: bool = Field(False, description="Continue previous search")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None and (not v or not v.strip()):
            raise ValueError("title must be a non-empty string")
        return v.strip() if v else None
