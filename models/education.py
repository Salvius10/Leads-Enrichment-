"""
EducationEntry model for storing education information from SignalHire.

This model represents individual education entries for prospects,
including school, degree, field of study, and graduation details.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DegreeType(Enum):
    """Types of degrees/education levels."""

    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORAL = "doctoral"
    CERTIFICATE = "certificate"
    DIPLOMA = "diploma"
    PROFESSIONAL = "professional"
    OTHER = "other"


class EducationStatus(Enum):
    """Status of education."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    INCOMPLETE = "incomplete"
    EXPECTED = "expected"


@dataclass
class EducationEntry:
    """Individual education entry for a prospect."""

    institution_name: str
    degree_type: DegreeType
    field_of_study: str | None = None
    degree_name: str | None = None  # e.g., "Bachelor of Science"
    start_date: str | None = None  # ISO format or partial like "2018" or "2018-09"
    end_date: str | None = None  # Graduation date or expected graduation
    status: EducationStatus = EducationStatus.COMPLETED
    gpa: str | None = None
    honors: str | None = None  # e.g., "Magna Cum Laude", "Dean's List"
    location: str | None = None
    activities: list[str] = None  # Clubs, organizations, etc.
    relevant_courses: list[str] = None
    description: str | None = None

    def __post_init__(self):
        """Validate education entry after initialization."""
        if not self.institution_name or not self.institution_name.strip():
            raise ValueError("Institution name is required")

        # Clean up string fields
        self.institution_name = self.institution_name.strip()

        if self.field_of_study:
            self.field_of_study = self.field_of_study.strip()

        if self.degree_name:
            self.degree_name = self.degree_name.strip()

        if self.gpa:
            self.gpa = self.gpa.strip()

        if self.honors:
            self.honors = self.honors.strip()

        if self.location:
            self.location = self.location.strip()

        if self.description:
            self.description = self.description.strip()

        # Initialize lists if None
        if self.activities is None:
            self.activities = []

        if self.relevant_courses is None:
            self.relevant_courses = []

        # Clean up lists
        self.activities = [
            activity.strip()
            for activity in self.activities
            if activity and activity.strip()
        ]
        self.relevant_courses = [
            course.strip()
            for course in self.relevant_courses
            if course and course.strip()
        ]

        # Validate date format (basic check)
        self._validate_date_format(self.start_date, "start_date")
        self._validate_date_format(self.end_date, "end_date")

        # Set status based on end_date and current date
        if self.status == EducationStatus.COMPLETED and self.end_date:
            try:
                end_year = int(self.end_date.split("-")[0])
                current_year = datetime.now().year
                if end_year > current_year:
                    self.status = EducationStatus.EXPECTED
            except (ValueError, IndexError):
                pass

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

    def get_duration_years(self) -> float | None:
        """Calculate duration in years (approximate)."""
        if not self.start_date or not self.end_date:
            return None

        try:
            start_year = int(self.start_date.split("-")[0])
            end_year = int(self.end_date.split("-")[0])

            # Basic calculation - could be more precise with months
            duration = end_year - start_year

            # Handle partial years if month info is available
            if "-" in self.start_date and "-" in self.end_date:
                start_parts = self.start_date.split("-")
                end_parts = self.end_date.split("-")

                if len(start_parts) >= 2 and len(end_parts) >= 2:
                    start_month = int(start_parts[1])
                    end_month = int(end_parts[1])

                    duration += (end_month - start_month) / 12.0

            return max(0.1, duration)  # At least 0.1 years

        except (ValueError, IndexError):
            return None

    def is_current_education(self) -> bool:
        """Check if this is current/ongoing education."""
        return self.status in [EducationStatus.IN_PROGRESS, EducationStatus.EXPECTED]

    def get_graduation_year(self) -> int | None:
        """Get graduation year if available."""
        if not self.end_date:
            return None

        try:
            return int(self.end_date.split("-")[0])
        except (ValueError, IndexError):
            return None

    def add_activity(self, activity: str) -> None:
        """Add an activity/organization to the education entry."""
        if not activity or not activity.strip():
            return

        activity = activity.strip()
        if activity not in self.activities:
            self.activities.append(activity)

    def add_course(self, course: str) -> None:
        """Add a relevant course to the education entry."""
        if not course or not course.strip():
            return

        course = course.strip()
        if course not in self.relevant_courses:
            self.relevant_courses.append(course)

    def get_degree_display_name(self) -> str:
        """Get formatted degree name for display."""
        if self.degree_name:
            return self.degree_name

        # Generate from degree_type and field_of_study
        type_names = {
            DegreeType.HIGH_SCHOOL: "High School Diploma",
            DegreeType.ASSOCIATE: "Associate Degree",
            DegreeType.BACHELOR: "Bachelor's Degree",
            DegreeType.MASTER: "Master's Degree",
            DegreeType.DOCTORAL: "Doctoral Degree",
            DegreeType.CERTIFICATE: "Certificate",
            DegreeType.DIPLOMA: "Diploma",
            DegreeType.PROFESSIONAL: "Professional Degree",
            DegreeType.OTHER: "Degree",
        }

        base_name = type_names.get(self.degree_type, "Degree")

        if self.field_of_study:
            return f"{base_name} in {self.field_of_study}"

        return base_name

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "institution_name": self.institution_name,
            "degree_type": self.degree_type.value,
            "field_of_study": self.field_of_study,
            "degree_name": self.degree_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status.value,
            "gpa": self.gpa,
            "honors": self.honors,
            "location": self.location,
            "activities": self.activities,
            "relevant_courses": self.relevant_courses,
            "description": self.description,
            "duration_years": self.get_duration_years(),
            "graduation_year": self.get_graduation_year(),
            "is_current": self.is_current_education(),
            "degree_display_name": self.get_degree_display_name(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EducationEntry":
        """Create EducationEntry from dictionary."""
        return cls(
            institution_name=data["institution_name"],
            degree_type=DegreeType(data["degree_type"]),
            field_of_study=data.get("field_of_study"),
            degree_name=data.get("degree_name"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            status=EducationStatus(data.get("status", "completed")),
            gpa=data.get("gpa"),
            honors=data.get("honors"),
            location=data.get("location"),
            activities=data.get("activities", []),
            relevant_courses=data.get("relevant_courses", []),
            description=data.get("description"),
        )

    def __str__(self) -> str:
        """String representation of education entry."""
        degree_name = self.get_degree_display_name()
        year_info = ""

        if self.get_graduation_year():
            year_info = f" ({self.get_graduation_year()})"
        elif self.is_current_education():
            year_info = " (Current)"

        return f"{degree_name} from {self.institution_name}{year_info}"
