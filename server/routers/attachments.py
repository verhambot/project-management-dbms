import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List

# Import CRUD modules
import crud.attachment as crud_attachment
import crud.issue as crud_issue
import crud.project as crud_project
from config import settings  # This gives us settings.UPLOAD_DIRECTORY

# Import Dependencies and Config
from dependencies import get_current_active_user
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

# Import Models
from models.attachment import Attachment, AttachmentCreate
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Authorization Helper Function ---
async def get_issue_and_check_read_access(
    issue_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Dependency to get an issue and verify user has read access.
    """
    db_issue = crud_issue.get_issue_by_id(issue_id)
    if not db_issue:
        logger.warning(f"Issue not found: {issue_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    project = crud_project.get_project_by_id(db_issue.project_id)
    if not project:
        logger.error(
            f"Orphaned issue {issue_id} links to non-existent project {db_issue.project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Issue data is inconsistent",
        )

    # Authorization logic:
    if current_user.role != "admin" and project.owner_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized for project {project.project_id} (to access issue {issue_id})."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project's resources",
        )

    return db_issue


# --- Endpoints ---


@router.post(
    "/by-issue/{issue_id}",
    response_model=Attachment,
    status_code=status.HTTP_201_CREATED,
)
async def upload_new_attachment(
    issue_id: int,
    file: UploadFile = File(...),
    # This dependency call handles auth and issue existence
    issue=Depends(get_issue_and_check_read_access),
    current_user: User = Depends(get_current_active_user),
):
    """
    Uploads a new file and attaches it to an issue.
    The user must have read-access to the issue's project.
    """
    logger.info(
        f"User {current_user.username} attempting to upload attachment to issue: {issue_id}"
    )

    # Generate a unique, safe filename.
    # We use UUID to prevent directory traversal and filename collisions.
    original_filename = file.filename or "unknown_file"
    # Sanitize filename (basic)
    safe_filename = "".join(
        c for c in original_filename if c.isalnum() or c in (".", "_", "-")
    ).strip()
    if not safe_filename:
        safe_filename = "attached_file"

    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    file_path = Path(unique_filename)
    full_file_path = settings.UPLOAD_DIRECTORY_NAME / file_path

    # Save the file to disk
    file_size_bytes = 0
    try:
        with full_file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Get file size
        file_size_bytes = full_file_path.stat().st_size

    except Exception as e:
        logger.exception(f"Failed to save uploaded file {full_file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save file.",
        )
    finally:
        file.file.close()

    # Create the database record
    attachment_data = AttachmentCreate(
        issue_id=issue_id,
        user_id=current_user.user_id,
        file_name=original_filename,
        file_path=str(file_path),  # Store the relative path
        file_type=file.content_type,
        file_size_bytes=file_size_bytes,
    )

    try:
        created_attachment = crud_attachment.create_attachment(
            attachment_in=attachment_data
        )
        if not created_attachment:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create attachment record.",
            )

        logger.info(
            f"Attachment {created_attachment.attachment_id} created for issue {issue_id}"
        )
        return created_attachment

    except (ValueError, Exception) as e:
        # If DB create fails, roll back by deleting the file we just saved
        logger.warning(
            f"Failed to create attachment DB record. Deleting orphaned file: {full_file_path}"
        )
        try:
            os.remove(full_file_path)
        except OSError as os_err:
            logger.error(
                f"CRITICAL: Failed to delete orphaned file {full_file_path}: {os_err}"
            )

        if isinstance(e, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal error occurred.",
            )


@router.get("/by-issue/{issue_id}", response_model=List[Attachment])
async def read_attachments_for_issue(
    issue_id: int,
    skip: int = 0,
    limit: int = 100,
    # This dependency call handles auth and issue existence
    issue=Depends(get_issue_and_check_read_access),
):
    """
    Retrieves all attachment metadata for a specific issue.
    The user must have read-access to the issue's project.
    """
    logger.debug(f"Fetching attachments for issue: {issue_id}")
    attachments = crud_attachment.get_attachments_by_issue_id(
        issue_id, skip=skip, limit=limit
    )

    # Add the full download URL to each attachment
    for att in attachments:
        att.download_url = f"/api/attachments/{att.attachment_id}/download"

    return attachments


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Downloads an attachment file.
    The user must have read-access to the issue's project.
    """
    logger.debug(
        f"User {current_user.username} attempting to download attachment: {attachment_id}"
    )

    # 1. Get attachment metadata
    attachment = crud_attachment.get_attachment_by_id(attachment_id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # 2. Check authorization
    await get_issue_and_check_read_access(attachment.issue_id, current_user)

    # 3. Construct file path and check if it exists
    full_file_path = Path(settings.UPLOAD_DIRECTORY_NAME) / Path(attachment.file_path)
    if not os.path.exists(full_file_path) or not os.path.isfile(full_file_path):
        logger.error(
            f"File not found on disk for attachment {attachment_id}: {full_file_path}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    # 4. Return the file
    return FileResponse(
        path=full_file_path,
        filename=attachment.file_name,  # This name is suggested to the user for saving
        media_type=attachment.file_type or "application/octet-stream",
        content_disposition_type="attachment",  # This forces a download dialog
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_attachment(
    attachment_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Deletes an attachment (record and file).
    Allowed for the file uploader, the project owner, or an admin.
    """
    logger.info(
        f"User {current_user.username} attempting to DELETE attachment ID: {attachment_id}"
    )

    # 1. Get the attachment
    db_attachment = crud_attachment.get_attachment_by_id(attachment_id)
    if not db_attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # 2. Get issue and project for authorization
    db_issue = crud_issue.get_issue_by_id(db_attachment.issue_id)
    project_owner_id = None
    if db_issue:
        project = crud_project.get_project_by_id(db_issue.project_id)
        if project:
            project_owner_id = project.owner_id
    else:
        logger.warning(
            f"Attachment {attachment_id} is on a non-existent issue {db_attachment.issue_id}."
        )
        # If we can't find the project owner, only allow admin or author
        if (
            current_user.role != "admin"
            and db_attachment.user_id != current_user.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this attachment",
            )

    # 3. Authorization Check
    if (
        current_user.role != "admin"
        and db_attachment.user_id != current_user.user_id
        and project_owner_id != current_user.user_id
    ):
        logger.warning(
            f"User {current_user.username} not authorized to DELETE attachment {attachment_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this attachment",
        )

    # 4. Perform the delete (CRUD function handles both DB and file)
    try:
        deleted = crud_attachment.delete_attachment(attachment_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found or could not be deleted",
            )

        logger.info(
            f"Attachment {attachment_id} deleted successfully by {current_user.username}."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except IOError as io_err:
        # Catch file deletion errors from the CRUD function
        logger.error(
            f"File system error while deleting attachment {attachment_id}: {io_err}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete attachment file from server"
        )
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred deleting attachment {attachment_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
