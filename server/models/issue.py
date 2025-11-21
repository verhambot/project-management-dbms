import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .attachment import Attachment
from .comment import Comment  # Import related models for detailed view
from .worklog import Worklog

# --- Issue Schemas ---


class IssueBase(BaseModel):
    """
    Base model for issue data.
    Contains common fields.
    """

    description: str = Field(
        ..., min_length=1, description="The main description of the issue"
    )

    # Validates against the CHECK constraint in the database
    issue_type: str = Field(
        "Task", description="Type of issue (Task, Bug, Story, Epic)"
    )
    priority: str = Field(
        "Medium", description="Priority level (Highest, High, Medium, Low, Lowest)"
    )
    status: str = Field(
        "To Do",
        description="Current status (To Do, In Progress, In Review, Done, Blocked)",
    )
    due_date: Optional[datetime.date] = None
    story_points: Optional[int] = Field(
        None, ge=0, description="Estimation points for the issue"
    )
    parent_issue_id: Optional[int] = Field(
        None, description="The ID of the parent issue (for sub-tasks)"
    )


class IssueCreate(IssueBase):
    """
    Schema for creating a new issue.
    Used in the POST request body.
    """

    project_id: int = Field(..., description="The project this issue belongs to")
    reporter_id: Optional[int] = Field(
        None, description="ID of the user reporting the issue (set from current user)"
    )
    assignee_id: Optional[int] = Field(
        None, description="ID of the user assigned to the issue"
    )
    sprint_id: Optional[int] = Field(
        None, description="ID of the sprint this issue belongs to"
    )


class IssueUpdate(BaseModel):
    """
    Schema for general-purpose updates to an issue.
    All fields are optional for partial updates.
    """

    description: Optional[str] = Field(None, min_length=1)
    issue_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[int] = None
    sprint_id: Optional[int] = None  # Use with caution, dedicated endpoint is better
    due_date: Optional[datetime.date] = None
    story_points: Optional[int] = Field(None, ge=0)
    parent_issue_id: Optional[int] = None  # Use with caution


# --- Specific Schemas for dedicated update endpoints ---


class IssueAssignSprint(BaseModel):
    """Schema specifically for assigning an issue to a sprint"""

    sprint_id: Optional[int] = Field(
        None, description="The ID of the sprint to assign to (null to unassign)"
    )


class IssueAssignUser(BaseModel):
    """Schema specifically for assigning an issue to a user"""

    assignee_id: Optional[int] = Field(
        None, description="The ID of the user to assign to (null to unassign)"
    )


class IssueUpdateStatus(BaseModel):
    """Schema specifically for updating issue status"""

    status: str = Field(..., description="The new status (To Do, In Progress, etc.)")


# --- Database and Response Schemas ---


class IssueInDBBase(IssueBase):
    """
    Base model for issue data as it exists in the database.
    Includes auto-generated fields.
    """

    issue_id: int
    project_id: int
    sprint_id: Optional[int]
    reporter_id: Optional[int]
    assignee_id: Optional[int]
    created_date: datetime.datetime
    updated_date: datetime.datetime

    class Config:
        """Allows creating this model from database records"""

        from_attributes = True


class Issue(IssueInDBBase):
    """
    Schema for returning standard issue data via the API.
    This is the "public" model for an issue.
    It can be expanded with JOINed data.
    """

    # Example fields you might add from JOINs in your CRUD function:
    reporter_username: Optional[str] = None
    assignee_username: Optional[str] = None
    project_key: Optional[str] = None
    sprint_name: Optional[str] = None
    parent_issue_description: Optional[str] = None  # Example


class IssueWithDetails(Issue):
    """
    Schema for returning a single issue with all its related details.
    Used for the "Get Issue by ID" endpoint.
    """

    comments: List[Comment] = []
    worklogs: List[Worklog] = []
    attachments: List[Attachment] = []
    total_hours_logged: float = Field(0.0, description="Sum of hours from all worklogs")

    # You could also add child_issues here if needed
    # child_issues: List[Issue] = []
