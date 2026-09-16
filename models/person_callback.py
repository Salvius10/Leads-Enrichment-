# Note: 'from __future__ import annotations' removed - breaks Pydantic v2 model resolution

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class PersonLocation(BaseModel):
    name: str = Field(..., description="Location name")


class PersonPhoto(BaseModel):
    url: HttpUrl = Field(..., description="Photo URL")


class PersonContact(BaseModel):
    type: Literal["email", "phone"] = Field(..., description="Contact type")
    value: str = Field(..., description="Contact value")
    rating: str = Field(..., description="Contact rating")
    sub_type: str = Field(
        ...,
        description="Contact subtype like work, personal, work_phone",
        alias="subType",
    )
    info: str | None = Field(None, description="Additional contact info")


class PersonSocial(BaseModel):
    type: str = Field(..., description="Social platform type like li, fb, tw")
    link: HttpUrl = Field(..., description="Social profile link")
    rating: str = Field(..., description="Social profile rating")


class PersonLanguage(BaseModel):
    name: str = Field(..., description="Language name")
    proficiency: str = Field(..., description="Language proficiency level")


class PersonCandidate(BaseModel):
    """Candidate data from SignalHire callback.

    Education and experience use dict to accept the raw API format
    (university/faculty/startedYear for education, company/position/started
    for experience) without strict schema validation.
    """

    model_config = {"extra": "allow"}

    uid: str = Field(..., description="Unique identifier")
    full_name: str = Field(..., description="Full name", alias="fullName")
    gender: str | None = Field(None, description="Gender")
    photo: PersonPhoto | None = Field(None, description="Profile photo")
    locations: list[PersonLocation] = Field(
        default_factory=list, description="Location history"
    )
    skills: list[str] = Field(default_factory=list, description="Skills list")
    education: list[dict[str, Any]] = Field(
        default_factory=list, description="Education history (raw API format)"
    )
    experience: list[dict[str, Any]] = Field(
        default_factory=list, description="Work experience (raw API format)"
    )
    contacts: list[PersonContact] = Field(
        default_factory=list, description="Contact information"
    )
    social: list[PersonSocial] = Field(
        default_factory=list, description="Social profiles"
    )
    head_line: str | None = Field(
        None, description="Profile headline", alias="headLine"
    )
    summary: str | None = Field(None, description="Profile summary")
    language: list[PersonLanguage] = Field(
        default_factory=list, description="Languages"
    )


class PersonCallbackItem(BaseModel):
    status: Literal[
        "success", "failed", "credits_are_over", "timeout_exceeded", "duplicate_query"
    ] = Field(..., description="Processing status")
    item: str = Field(..., description="Original item that was processed")
    candidate: PersonCandidate | None = Field(
        None, description="Candidate data if successful"
    )


PersonCallbackData = list[PersonCallbackItem]
