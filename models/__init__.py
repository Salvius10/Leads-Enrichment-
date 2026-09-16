"""Pydantic models for SignalHire Agent."""

from .contact_info import ContactInfo
from .credit_usage import CreditUsage
from .education import EducationEntry as Education, DegreeType as EducationLevel
from .exceptions import (
    DataValidationError,
    SignalHireAPIError,
    SignalHireError,
    RateLimitError,
    AuthenticationError,
)
from .experience import ExperienceEntry as Experience, EmploymentType as ExperienceType
from .operations import (
    BaseOperation as Operation,
    OperationType,
    OperationStatus,
    SearchOp,
    RevealOp,
    WorkflowOp,
)
from .person_callback import PersonCallbackData, PersonCallbackItem
from .prospect import Prospect
from .search_criteria import SearchCriteria

__all__ = [
    # Contact info
    "ContactInfo",
    # Credits
    "CreditUsage",
    # Education
    "Education",
    "EducationLevel",
    # Exceptions
    "DataValidationError",
    "SignalHireAPIError",
    "SignalHireError",
    "RateLimitError",
    "AuthenticationError",
    # Experience
    "Experience",
    "ExperienceType",
    # Operations
    "Operation",
    "OperationType",
    "OperationStatus",
    "SearchOp",
    "RevealOp",
    "WorkflowOp",
    # Person callback
    "PersonCallbackData",
    "PersonCallbackItem",
    # Prospect
    "Prospect",
    # Search criteria
    "SearchCriteria",
]
