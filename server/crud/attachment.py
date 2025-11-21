import logging
import os
from pathlib import Path
from typing import List, Optional

import mysql.connector
from config import settings
from database import db_utils
from models.attachment import Attachment, AttachmentCreate

logger = logging.getLogger(__name__)


ATTACHMENT_COLUMNS = """
    a.attachment_id, a.issue_id, a.user_id, a.file_name,
    a.file_path, a.file_type, a.file_size_bytes, a.uploaded_at,
    u.username as uploader_username
"""
ATTACHMENT_JOIN = """
    FROM Attachment a
    LEFT JOIN User u ON a.user_id = u.user_id
"""

# Note: For 'uploader_username' to be included in the response,
# you must add `uploader_username: Optional[str] = None`
# to the `Attachment` model in `server/models/attachment.py`.


def create_attachment(attachment_in: AttachmentCreate) -> Optional[Attachment]:
    """
    Creates a new attachment record in the database.
    This function is called *after* the file has been saved to disk.
    The 'file_path' in attachment_in is the relative path for storage.
    """
    query = """
        INSERT INTO Attachment (issue_id, user_id, file_name, file_path, file_type, file_size_bytes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (
        attachment_in.issue_id,
        attachment_in.user_id,
        attachment_in.file_name,
        attachment_in.file_path,
        attachment_in.file_type,
        attachment_in.file_size_bytes,
    )

    try:
        result = db_utils.execute_query(query, params, is_commit=True)
        attachment_id = result.get("last_insert_id")

        if attachment_id:
            return get_attachment_by_id(attachment_id)
        return None
    except mysql.connector.Error as err:
        logger.error(f"Error creating attachment record in DB: {err}")
        if err.errno == 1452:
            raise ValueError(f"Issue with ID {attachment_in.issue_id} not found.")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred creating attachment record: {e}")
        raise


def get_attachment_by_id(attachment_id: int) -> Optional[Attachment]:
    """Retrieves a single attachment's metadata by its ID, joining with User."""
    query = f"SELECT {ATTACHMENT_COLUMNS} {ATTACHMENT_JOIN} WHERE a.attachment_id = %s"
    result = db_utils.execute_query(query, (attachment_id,), fetch_one=True)

    return Attachment.model_validate(result) if result else None


def get_attachments_by_issue_id(
    issue_id: int, skip: int = 0, limit: int = 100
) -> List[Attachment]:
    """
    Retrieves a paginated list of all attachments for a specific issue.
    This function was required by crud/issue.py.
    """
    query = f"""
        SELECT {ATTACHMENT_COLUMNS} {ATTACHMENT_JOIN}
        WHERE a.issue_id = %s
        ORDER BY a.uploaded_at DESC
        LIMIT %s OFFSET %s
    """
    results = db_utils.execute_query(query, (issue_id, limit, skip))

    if isinstance(results, list):
        return [Attachment.model_validate(row) for row in results]
    return []


def delete_attachment(attachment_id: int) -> bool:
    """
    Deletes an attachment record from the database AND its corresponding
    file from the filesystem.
    Returns True if the record was deleted.
    """
    # 1. Get the attachment metadata first to find the file_path
    attachment = get_attachment_by_id(attachment_id)
    if not attachment:
        logger.warning(f"Attachment {attachment_id} not found. Cannot delete.")
        return False  # Not found

    # 2. Delete the database record
    query = "DELETE FROM Attachment WHERE attachment_id = %s"
    try:
        result = db_utils.execute_query(query, (attachment_id,), is_commit=True)
        rows_affected = result.get("rows_affected", 0)

        if rows_affected > 0:
            # 3. If DB deletion was successful, delete the file from disk
            try:
                # Construct the full, absolute path to the file
                # settings.UPLOAD_DIRECTORY_NAME is the 'uploads/' folder
                # attachment.file_path is the relative filename (e.g., 'unique-id-file.png')
                full_file_path = Path(settings.UPLOAD_DIRECTORY_NAME) / Path(
                    attachment.file_path
                )

                if os.path.exists(full_file_path) and os.path.isfile(full_file_path):
                    os.remove(full_file_path)
                    logger.info(f"Successfully deleted file: {full_file_path}")
                else:
                    logger.warning(
                        f"File not found on disk, but DB record deleted: {full_file_path}"
                    )

            except OSError as os_err:
                # Log the error, but don't re-raise.
                # The DB record is gone, which is the most important part.
                # We can have a separate cleanup job for orphaned files.
                logger.error(
                    f"Error deleting file {full_file_path} from disk: {os_err}"
                )

            return True  # DB record was successfully deleted
        else:
            return False  # No record was deleted

    except mysql.connector.Error as err:
        logger.error(f"Error deleting attachment {attachment_id} from DB: {err}")
        raise
    except Exception as e:
        logger.error(
            f"An unexpected error occurred deleting attachment {attachment_id}: {e}"
        )
        raise
