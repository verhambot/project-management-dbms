import logging
from typing import List, Optional

import mysql.connector
from database import db_utils
from models.comment import Comment, CommentCreate, CommentUpdate

logger = logging.getLogger(__name__)

# --- Base Query Components ---
COMMENT_COLUMNS = """
    c.comment_id, c.issue_id, c.user_id, c.comment_text,
    c.created_at, c.updated_at,
    u.username as author_username
"""
COMMENT_JOIN = """
    FROM Comment c
    LEFT JOIN User u ON c.user_id = u.user_id
"""

# Note: For 'author_username' to be included in the response,
# you must add `author_username: Optional[str] = None`
# to the `Comment` model in `server/models/comment.py`.


def create_comment(comment_in: CommentCreate, user_id: int) -> Optional[Comment]:
    """
    Creates a new comment for an issue using the AddComment stored procedure.
    """
    query = "CALL AddComment(%s, %s, %s, @p_comment_id)"
    params = (comment_in.issue_id, user_id, comment_in.comment_text)

    conn = None
    cursor = None
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(query, params)

        # Fetch the OUT parameter
        cursor.execute("SELECT @p_comment_id AS comment_id")
        result = cursor.fetchone()

        conn.commit()

        comment_id = result.get("comment_id") if result else None

        if comment_id:
            # The after_comment_insert trigger handles updating Issue.updated_date
            return get_comment_by_id(comment_id)
        return None

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        logger.error(f"Error calling AddComment procedure: {err}")
        # Check for foreign key constraint fail (e.g., issue not found)
        if err.errno == 1452:  # Cannot add or update a child row
            raise ValueError(f"Issue with ID {comment_in.issue_id} not found.")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"An unexpected error occurred creating comment: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_comment_by_id(comment_id: int) -> Optional[Comment]:
    """Retrieves a single comment by its ID, joining with User."""
    query = f"SELECT {COMMENT_COLUMNS} {COMMENT_JOIN} WHERE c.comment_id = %s"
    result = db_utils.execute_query(query, (comment_id,), fetch_one=True)

    return Comment.model_validate(result) if result else None


def get_comments_by_issue_id(
    issue_id: int, skip: int = 0, limit: int = 100
) -> List[Comment]:
    """
    Retrieves a paginated list of all comments for a specific issue.
    Demonstrates WHERE, JOIN, ORDER BY, LIMIT, and OFFSET.
    """
    query = f"""
        SELECT {COMMENT_COLUMNS} {COMMENT_JOIN}
        WHERE c.issue_id = %s
        ORDER BY c.created_at ASC
        LIMIT %s OFFSET %s
    """
    results = db_utils.execute_query(query, (issue_id, limit, skip))

    return [Comment.model_validate(row) for row in results] if results else []


def update_comment(comment_id: int, comment_in: CommentUpdate) -> Optional[Comment]:
    """
    Updates an existing comment's text.
    """
    query = "UPDATE Comment SET comment_text = %s WHERE comment_id = %s"
    params = (comment_in.comment_text, comment_id)

    try:
        db_utils.execute_query(query, params, is_commit=True)
        # The after_comment_update trigger in SQL handles updating Issue.updated_date
        return get_comment_by_id(comment_id)
    except mysql.connector.Error as err:
        logger.error(f"Error updating comment {comment_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred updating comment {comment_id}: {e}")
        raise


def delete_comment(comment_id: int) -> bool:
    """
    Deletes a comment from the database.
    Returns True if a comment was deleted.
    """
    query = "DELETE FROM Comment WHERE comment_id = %s"
    try:
        result = db_utils.execute_query(query, (comment_id,), is_commit=True)
        # Note: Deleting a comment does *not* fire our trigger,
        # so Issue.updated_date is not modified. This is generally fine.
        return result.get("rows_affected", 0) > 0
    except mysql.connector.Error as err:
        logger.error(f"Error deleting comment {comment_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred deleting comment {comment_id}: {e}")
        raise
