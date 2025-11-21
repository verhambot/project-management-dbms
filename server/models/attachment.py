import datetime
from typing import Optional

from pydantic import BaseModel, Field

# --- Attachment Schemas ---


class AttachmentBase(BaseModel):
    """
    Base model for attachment metadata.
    Contains common fields.
    """

    file_name: str = Field(
        ..., max_length=255, description="The original name of the uploaded file"
    )
    file_type: Optional[str] = Field(
        None, max_length=100, description="The MIME type of the file (e.g., image/png)"
    )
    file_size_bytes: Optional[int] = Field(
        None, ge=0, description="The size of the file in bytes"
    )


class AttachmentCreate(AttachmentBase):
    """
    Schema used when creating an attachment record in the database.
    The path is set internally by the server.
    """

    issue_id: int = Field(..., description="The issue this attachment belongs to")
    user_id: Optional[int] = Field(
        None, description="The user who uploaded the file (set from current user)"
    )

    # This file_path is the *relative* path stored in the DB (e.g., "unique-id-filename.png")
    # The full server path is constructed using the UPLOAD_DIRECTORY setting
    file_path: str = Field(
        ..., description="The server-side path where the file is stored"
    )


class AttachmentInDBBase(AttachmentBase):
    """
    Base model for attachment data as it exists in the database.
    Includes auto-generated fields.
    """

    attachment_id: int
    issue_id: int
    user_id: Optional[int]
    file_path: str
    uploaded_at: datetime.datetime

    class Config:
        """Allows creating this model from database records"""

        from_attributes = True


class Attachment(AttachmentInDBBase):
    """
    Schema for returning attachment metadata via the API.
    This is the "public" model for an attachment.
    """

    # This field can be dynamically generated in the router
    # to provide a direct download link to the client.
    download_url: Optional[str] = Field(
        None, description="A dynamically generated URL to download the file"
    )

    # Example field you might add from a JOIN in your CRUD function:
    uploader_username: Optional[str] = None
    pass
