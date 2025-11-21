import datetime
from typing import Optional

from pydantic import BaseModel, Field

# --- Comment Schemas ---


class CommentBase(BaseModel):
    """
    Base model for comment data.
    Contains the core field.
    """

    comment_text: str = Field(
        ..., min_length=1, description="The text content of the comment"
    )


class CommentCreate(CommentBase):
    """
    Schema for creating a new comment.
    Used in the POST request body.
    """

    issue_id: int = Field(..., description="The issue this comment is on")
    user_id: Optional[int] = Field(
        None, description="The user posting the comment (set from current user)"
    )


class CommentUpdate(BaseModel):
    """
    Schema for updating an existing comment.
    """

    comment_text: str = Field(
        ..., min_length=1, description="The new text for the comment"
    )


class CommentInDBBase(CommentBase):
    """
    Base model for comment data as it exists in the database.
    Includes auto-generated fields.
    """

    comment_id: int
    issue_id: int
    user_id: Optional[int]
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None  # Tracks edits

    class Config:
        """Allows creating this model from database records"""

        from_attributes = True


class Comment(CommentInDBBase):
    """
    Schema for returning comment data via the API.
    This is the "public" model for a comment.
    """

    # Example field you might add from a JOIN in your CRUD function:
    author_username: Optional[str] = None
    pass
