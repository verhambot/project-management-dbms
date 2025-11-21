import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

# --- Worklog Schemas ---


class WorklogBase(BaseModel):
    """
    Base model for worklog data.
    Contains common fields.
    """

    # Use float for hours, but the DB uses DECIMAL(5, 2)
    hours_logged: float = Field(..., gt=0, description="Hours logged, must be positive")
    work_date: datetime.date = Field(..., description="The date the work was performed")
    description: Optional[str] = None

    @validator("hours_logged")
    def hours_must_be_positive_and_rounded(cls, v):
        """Validates that hours are positive and rounds to 2 decimal places."""
        if v <= 0:
            raise ValueError("Hours logged must be positive")
        # Round to 2 decimal places to match DB precision
        return round(v, 2)


class WorklogCreate(WorklogBase):
    """
    Schema for creating a new worklog entry.
    Used in the POST request body.
    """

    issue_id: int = Field(..., description="The issue this worklog is for")
    user_id: Optional[int] = Field(
        None, description="The user logging the work (set from current user)"
    )


class WorklogUpdate(BaseModel):
    """
    Schema for updating an existing worklog entry.
    All fields are optional for partial updates.
    """

    hours_logged: Optional[float] = Field(None, gt=0)
    work_date: Optional[datetime.date] = None
    description: Optional[str] = None

    @validator("hours_logged")
    def hours_must_be_positive_optional(cls, v):
        """Validates optional hours_logged field."""
        if v is not None:
            if v <= 0:
                raise ValueError("Hours logged must be positive")
            return round(v, 2)
        return v


class WorklogInDBBase(WorklogBase):
    """
    Base model for worklog data as it exists in the database.
    Includes auto-generated fields.
    """

    worklog_id: int
    issue_id: int
    user_id: Optional[int]
    created_at: datetime.datetime

    class Config:
        """Allows creating this model from database records"""

        from_attributes = True


class Worklog(WorklogInDBBase):
    """
    Schema for returning worklog data via the API.
    This is the "public" model for a worklog.
    """

    # Example field you might add from a JOIN in your CRUD function:
    logger_username: Optional[str] = None
    pass
