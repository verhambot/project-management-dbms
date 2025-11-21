import datetime
from typing import Optional

from pydantic import BaseModel, Field

# --- Project Schemas ---


class ProjectBase(BaseModel):
    """
    Base model for project data.
    Contains all common fields.
    """

    # Regex pattern ensures the key is uppercase alphanumeric and 1-10 chars
    project_key: str = Field(
        ...,
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z0-9]+$",
        description="Short uppercase alphanumeric key (e.g., DEMO)",
    )
    project_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None

    # Validates against the CHECK constraint in the database
    status: str = Field(
        "planning", description="Project status (planning, active, completed, archived)"
    )


class ProjectCreate(ProjectBase):
    """
    Schema for creating a new project.
    Used in the POST request body.
    """

    # The owner_id will be set by the endpoint, often from the current user
    owner_id: Optional[int] = Field(
        None, description="ID of the user creating/owning the project"
    )


class ProjectUpdate(BaseModel):
    """
    Schema for updating a project.
    All fields are optional for partial updates (PATCH/PUT).
    """

    project_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    status: Optional[str] = Field(None, description="Project status")
    owner_id: Optional[int] = None
    # Note: Changing project_key is generally discouraged and omitted here.


class ProjectInDBBase(ProjectBase):
    """
    Base model for project data as it exists in the database.
    Includes auto-generated fields.
    """

    project_id: int
    owner_id: Optional[int]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        """Allows creating this model from database records"""

        from_attributes = True


class Project(ProjectInDBBase):
    """
    Schema for returning project data via the API.
    This is the "public" model for a project.
    """

    # This model could be expanded to include related data, e.g.:
    # owner_username: Optional[str] = None
    # issue_count: Optional[int] = None
    pass
