"""
Operation models for tracking SignalHire agent workflows.

These models represent the various operations that can be performed,
including search operations, reveal operations, and their status tracking.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OperationStatus(Enum):
    """Status of an operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some results, but not all


class OperationType(Enum):
    """Types of operations."""

    SEARCH = "search"
    REVEAL = "reveal"
    BULK_REVEAL = "bulk_reveal"
    EXPORT = "export"
    WORKFLOW = "workflow"  # Combined operations


@dataclass
class BaseOperation:
    """Base class for all operations."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: OperationType = OperationType.SEARCH
    status: OperationStatus = OperationStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate operation after initialization."""
        if not self.id:
            self.id = str(uuid.uuid4())

    def start(self) -> None:
        """Mark operation as started."""
        self.status = OperationStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def complete(self) -> None:
        """Mark operation as completed."""
        self.status = OperationStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()

    def fail(self, error_message: str) -> None:
        """Mark operation as failed."""
        self.status = OperationStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now().isoformat()

    def cancel(self) -> None:
        """Mark operation as cancelled."""
        self.status = OperationStatus.CANCELLED
        self.completed_at = datetime.now().isoformat()

    def get_duration_seconds(self) -> float | None:
        """Get operation duration in seconds."""
        if not self.started_at or not self.completed_at:
            return None

        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            return (end - start).total_seconds()
        except ValueError:
            return None

    def is_active(self) -> bool:
        """Check if operation is currently active."""
        return self.status in [OperationStatus.PENDING, OperationStatus.RUNNING]

    def is_finished(self) -> bool:
        """Check if operation is finished (completed, failed, or cancelled)."""
        return self.status in [
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
            OperationStatus.PARTIAL,
        ]


@dataclass
class SearchOp(BaseOperation):
    """Search operation for finding prospects on SignalHire."""

    type: OperationType = field(default=OperationType.SEARCH, init=False)
    search_criteria: dict[str, Any] | None = None
    results_count: int = 0
    total_available: int | None = None
    prospect_ids: list[str] = field(default_factory=list)
    search_url: str | None = None
    credits_estimated: int = 0
    page_size: int = 25
    max_results: int | None = None

    def __post_init__(self):
        """Validate search operation after initialization."""
        super().__post_init__()

        if self.search_criteria is None:
            self.search_criteria = {}

        if not isinstance(self.prospect_ids, list):
            self.prospect_ids = []

    def add_prospect(self, prospect_id: str) -> None:
        """Add a prospect ID to the results."""
        if prospect_id and prospect_id not in self.prospect_ids:
            self.prospect_ids.append(prospect_id)
            self.results_count = len(self.prospect_ids)

    def add_prospects(self, prospect_ids: list[str]) -> None:
        """Add multiple prospect IDs to the results."""
        for prospect_id in prospect_ids:
            self.add_prospect(prospect_id)

    def get_completion_percentage(self) -> float:
        """Get completion percentage based on max_results or total_available."""
        if self.max_results:
            return min(100.0, (self.results_count / self.max_results) * 100)
        if self.total_available:
            return min(100.0, (self.results_count / self.total_available) * 100)
        return 0.0 if self.results_count == 0 else 100.0

    def estimate_remaining_credits(self) -> int:
        """Estimate credits needed for remaining prospects."""
        if self.max_results:
            remaining = max(0, self.max_results - self.results_count)
        elif self.total_available:
            remaining = max(0, self.total_available - self.results_count)
        else:
            remaining = 0

        return remaining  # 1 credit per prospect for reveal


@dataclass
class RevealOp(BaseOperation):
    """Reveal operation for getting contact info for prospects."""

    type: OperationType = field(default=OperationType.REVEAL, init=False)
    prospect_ids: list[str] = field(default_factory=list)
    revealed_contacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_reveals: dict[str, str] = field(default_factory=dict)  # prospect_id -> error
    credits_used: int = 0
    credits_available: int | None = None
    batch_size: int = 10
    use_bulk_export: bool = False
    export_format: str = "csv"

    def __post_init__(self):
        """Validate reveal operation after initialization."""
        super().__post_init__()

        if not isinstance(self.prospect_ids, list):
            self.prospect_ids = []

        if not isinstance(self.revealed_contacts, dict):
            self.revealed_contacts = {}

        if not isinstance(self.failed_reveals, dict):
            self.failed_reveals = {}

    def add_prospect_to_reveal(self, prospect_id: str) -> None:
        """Add a prospect ID to be revealed."""
        if prospect_id and prospect_id not in self.prospect_ids:
            self.prospect_ids.append(prospect_id)

    def reveal_success(
        self, prospect_id: str, contact_data: dict[str, Any], credits_used: int = 1
    ) -> None:
        """Mark a prospect reveal as successful."""
        self.revealed_contacts[prospect_id] = contact_data
        self.credits_used += credits_used

        # Remove from failed if it was there
        if prospect_id in self.failed_reveals:
            del self.failed_reveals[prospect_id]

    def reveal_failure(self, prospect_id: str, error_message: str) -> None:
        """Mark a prospect reveal as failed."""
        self.failed_reveals[prospect_id] = error_message

        # Remove from revealed if it was there
        if prospect_id in self.revealed_contacts:
            del self.revealed_contacts[prospect_id]

    def get_success_count(self) -> int:
        """Get number of successful reveals."""
        return len(self.revealed_contacts)

    def get_failure_count(self) -> int:
        """Get number of failed reveals."""
        return len(self.failed_reveals)

    def get_completion_percentage(self) -> float:
        """Get completion percentage."""
        total = len(self.prospect_ids)
        if total == 0:
            return 0.0

        completed = self.get_success_count() + self.get_failure_count()
        return (completed / total) * 100

    def get_success_rate(self) -> float:
        """Get success rate percentage."""
        total_completed = self.get_success_count() + self.get_failure_count()
        if total_completed == 0:
            return 0.0

        return (self.get_success_count() / total_completed) * 100

    def can_continue(self) -> bool:
        """Check if reveal operation can continue (has credits and prospects)."""
        if (
            self.credits_available is not None
            and self.credits_used >= self.credits_available
        ):
            return False

        remaining_prospects = (
            len(self.prospect_ids) - self.get_success_count() - self.get_failure_count()
        )
        return remaining_prospects > 0


@dataclass
class WorkflowOp(BaseOperation):
    """Workflow operation combining multiple steps (search + reveal + export)."""

    type: OperationType = field(default=OperationType.WORKFLOW, init=False)
    search_op_id: str | None = None
    reveal_op_id: str | None = None
    export_op_id: str | None = None
    workflow_config: dict[str, Any] = field(default_factory=dict)
    current_step: str = "search"
    steps_completed: list[str] = field(default_factory=list)
    final_output_path: str | None = None

    def __post_init__(self):
        """Validate workflow operation after initialization."""
        super().__post_init__()

        if not isinstance(self.workflow_config, dict):
            self.workflow_config = {}

        if not isinstance(self.steps_completed, list):
            self.steps_completed = []

    def complete_step(self, step_name: str) -> None:
        """Mark a workflow step as completed."""
        if step_name not in self.steps_completed:
            self.steps_completed.append(step_name)

    def set_current_step(self, step_name: str) -> None:
        """Set the current workflow step."""
        self.current_step = step_name

    def get_progress_percentage(self) -> float:
        """Get workflow progress percentage."""
        total_steps = len(["search", "reveal", "export"])
        completed_steps = len(self.steps_completed)
        return (completed_steps / total_steps) * 100

    def is_step_completed(self, step_name: str) -> bool:
        """Check if a specific step is completed."""
        return step_name in self.steps_completed


# Utility functions for operation management


def create_search_operation(
    search_criteria: dict[str, Any], max_results: int | None = None
) -> SearchOp:
    """Create a new search operation."""
    return SearchOp(
        search_criteria=search_criteria,
        max_results=max_results,
        metadata={"created_by": "signalhire_agent"},
    )


def create_reveal_operation(
    prospect_ids: list[str], use_bulk_export: bool = False
) -> RevealOp:
    """Create a new reveal operation."""
    return RevealOp(
        prospect_ids=prospect_ids.copy(),
        use_bulk_export=use_bulk_export,
        metadata={"created_by": "signalhire_agent"},
    )


def create_workflow_operation(
    search_criteria: dict[str, Any], workflow_config: dict[str, Any]
) -> WorkflowOp:
    """Create a new workflow operation."""
    return WorkflowOp(
        workflow_config=workflow_config,
        metadata={"created_by": "signalhire_agent", "search_criteria": search_criteria},
    )
