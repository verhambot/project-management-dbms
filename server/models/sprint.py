import datetime
from typing import Optional

from pydantic import BaseModel, Field

# --- Sprint Schemas ---


class SprintBase(BaseModel):
    """
    Base model for sprint data.
    Contains common fields.
    """

    sprint_name: str = Field(..., min_length=1, max_length=255)
    goal: Optional[str] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None

    # Validates against the CHECK constraint in the database
    status: str = Field(
        "future", description="Sprint status (future, active, completed)"
    )


class SprintCreate(SprintBase):
    """
    Schema for creating a new sprint.
    Requires project_id to link it to a project.
    """

    project_id: int = Field(..., description="The project this sprint belongs to")


class SprintUpdate(BaseModel):
    """
    Schema for updating a sprint.
    All fields are optional for partial updates.
    """

    sprint_name: Optional[str] = Field(None, min_length=1, max_length=255)
    goal: Optional[str] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    status: Optional[str] = Field(None, description="Sprint status")
    # project_id is generally not updatable


class SprintInDBBase(SprintBase):
    """
    Base model for sprint data as it exists in the database.
    Includes auto-generated fields.
    """

    sprint_id: int
    project_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        """Allows creating this model from database records"""

        from_attributes = True


class Sprint(SprintInDBBase):
    """
    Schema for returning sprint data via the API.
    This is the "public" model for a sprint.
    """

    pass
