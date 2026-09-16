"""
ExperienceEntry model for storing work experience information from SignalHire.

This model represents individual work experience entries for prospects,
including company, role, duration, and description details.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EmploymentType(Enum):
    """Types of employment."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"
    OTHER = "other"


@dataclass
class ExperienceEntry:
    """Individual work experience entry for a prospect."""

    company_name: str
    job_title: str
    start_date: str | None = None  # ISO format or partial like "2023" or "2023-06"
    end_date: str | None = None  # None means current position
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    location: str | None = None
    description: str | None = None
    company_size: str | None = None
    industry: str | None = None
    skills: list[str] = None
    is_current: bool = False

    def __post_init__(self):
        """Validate experience entry after initialization."""
        if not self.company_name or not self.company_name.strip():
            raise ValueError("Company name is required")

        if not self.job_title or not self.job_title.strip():
            raise ValueError("Job title is required")

        # Clean up string fields
        self.company_name = self.company_name.strip()
        self.job_title = self.job_title.strip()

        if self.location:
            self.location = self.location.strip()

        if self.description:
            self.description = self.description.strip()

        if self.company_size:
            self.company_size = self.company_size.strip()

        if self.industry:
            self.industry = self.industry.strip()

        # Initialize skills list if None
        if self.skills is None:
            self.skills = []

        # Clean up skills
        self.skills = [
            skill.strip() for skill in self.skills if skill and skill.strip()
        ]

        # Set is_current based on end_date
        if self.end_date is None:
            self.is_current = True

        # Validate date format (basic check)
        self._validate_date_format(self.start_date, "start_date")
        self._validate_date_format(self.end_date, "end_date")

    def _validate_date_format(self, date_str: str | None, field_name: str) -> None:
        """Validate date format (allows partial dates)."""
        if not date_str:
            return

        # Accept formats: "2023", "2023-06", "2023-06-15"
        valid_formats = ["%Y", "%Y-%m", "%Y-%m-%d"]  # 2023  # 2023-06  # 2023-06-15

        for fmt in valid_formats:
            try:
                datetime.strptime(date_str, fmt)
                return
            except ValueError:
                continue

        raise ValueError(
            f"Invalid {field_name} format: {date_str}. Use YYYY, YYYY-MM, or YYYY-MM-DD"
        )

    def get_duration_months(self) -> int | None:
        """Calculate duration in months (approximate)."""
        if not self.start_date:
            return None

        try:
            # Parse start date
            start = self._parse_date_to_first_day(self.start_date)

            # Parse end date or use current date
            if self.end_date:
                end = self._parse_date_to_last_day(self.end_date)
            else:
                end = datetime.now()

            # Calculate difference in months (approximate)
            years_diff = end.year - start.year
            months_diff = end.month - start.month
            total_months = years_diff * 12 + months_diff

            return max(1, total_months)  # At least 1 month

        except (ValueError, TypeError):
            return None

    def _parse_date_to_first_day(self, date_str: str) -> datetime:
        """Parse date string to first day of the period."""
        if len(date_str) == 4:  # "2023"
            return datetime(int(date_str), 1, 1)
        if len(date_str) == 7:  # "2023-06"
            year, month = date_str.split("-")
            return datetime(int(year), int(month), 1)
        # "2023-06-15"
        return datetime.strptime(date_str, "%Y-%m-%d")

    def _parse_date_to_last_day(self, date_str: str) -> datetime:
        """Parse date string to last day of the period."""
        if len(date_str) == 4:  # "2023"
            return datetime(int(date_str), 12, 31)
        if len(date_str) == 7:  # "2023-06"
            year, month = date_str.split("-")
            # Get last day of month
            if month == "12":
                next_month = datetime(int(year) + 1, 1, 1)
            else:
                next_month = datetime(int(year), int(month) + 1, 1)
            from datetime import timedelta

            return next_month - timedelta(days=1)
        # "2023-06-15"
        return datetime.strptime(date_str, "%Y-%m-%d")

    def add_skill(self, skill: str) -> None:
        """Add a skill to the experience entry."""
        if not skill or not skill.strip():
            return

        skill = skill.strip()
        if skill not in self.skills:
            self.skills.append(skill)

    def remove_skill(self, skill: str) -> None:
        """Remove a skill from the experience entry."""
        if skill in self.skills:
            self.skills.remove(skill)

    def get_formatted_duration(self) -> str:
        """Get human-readable duration string."""
        months = self.get_duration_months()
        if not months:
            return "Unknown duration"

        if months < 12:
            return f"{months} month{'s' if months != 1 else ''}"

        years = months // 12
        remaining_months = months % 12

        if remaining_months == 0:
            return f"{years} year{'s' if years != 1 else ''}"

        return f"{years} year{'s' if years != 1 else ''}, {remaining_months} month{'s' if remaining_months != 1 else ''}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "company_name": self.company_name,
            "job_title": self.job_title,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "employment_type": self.employment_type.value,
            "location": self.location,
            "description": self.description,
            "company_size": self.company_size,
            "industry": self.industry,
            "skills": self.skills,
            "is_current": self.is_current,
            "duration_months": self.get_duration_months(),
            "formatted_duration": self.get_formatted_duration(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExperienceEntry":
        """Create ExperienceEntry from dictionary."""
        return cls(
            company_name=data["company_name"],
            job_title=data["job_title"],
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            employment_type=EmploymentType(data.get("employment_type", "full_time")),
            location=data.get("location"),
            description=data.get("description"),
            company_size=data.get("company_size"),
            industry=data.get("industry"),
            skills=data.get("skills", []),
            is_current=data.get("is_current", False),
        )

    def __str__(self) -> str:
        """String representation of experience entry."""
        duration = self.get_formatted_duration()
        current_indicator = " (Current)" if self.is_current else ""
        return (
            f"{self.job_title} at {self.company_name} ({duration}){current_indicator}"
        )
