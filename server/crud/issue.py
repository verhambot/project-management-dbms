import logging
from typing import List, Optional

import crud.attachment as crud_attachment

# We will need other CRUD modules for the detailed view
import crud.comment as crud_comment
import crud.worklog as crud_worklog
import mysql.connector
from database import db_utils
from models.issue import (
    Issue,
    IssueAssignSprint,
    IssueAssignUser,
    IssueCreate,
    IssueUpdate,
    IssueUpdateStatus,
    IssueWithDetails,
)

logger = logging.getLogger(__name__)

# --- Base Query Components ---
# Define common joins for fetching detailed issue data
# This demonstrates multiple JOINs as required
ISSUE_COLUMNS = """
    i.issue_id, i.project_id, i.sprint_id, i.description,
    i.issue_type, i.priority, i.status, i.reporter_id, i.assignee_id,
    i.created_date, i.due_date, i.updated_date, i.story_points, i.parent_issue_id,
    p.project_key,
    s.sprint_name,
    reporter.username AS reporter_username,
    assignee.username AS assignee_username
"""
ISSUE_JOINS = """
    FROM Issue i
    JOIN Project p ON i.project_id = p.project_id
    LEFT JOIN Sprint s ON i.sprint_id = s.sprint_id
    LEFT JOIN User reporter ON i.reporter_id = reporter.user_id
    LEFT JOIN User assignee ON i.assignee_id = assignee.user_id
"""


def create_issue(issue_in: IssueCreate, reporter_id: int) -> Optional[Issue]:
    """
    Creates a new issue by calling the CreateIssue stored procedure.
    The reporter_id is taken from the current authenticated user.
    """
    query = "CALL CreateIssue(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, @p_issue_id)"
    params = (
        issue_in.project_id,
        issue_in.description,
        issue_in.issue_type,
        issue_in.priority,
        reporter_id,  # Set from the authenticated user
        issue_in.assignee_id,
        issue_in.sprint_id,
        issue_in.due_date,
        issue_in.story_points,
        issue_in.parent_issue_id,
    )

    conn = None
    cursor = None
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(query, params)

        cursor.execute("SELECT @p_issue_id AS issue_id")
        result = cursor.fetchone()

        conn.commit()

        issue_id = result.get("issue_id") if result else None

        if issue_id:
            return get_issue_by_id(issue_id)
        return None

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        logger.error(f"Error calling CreateIssue procedure: {err}")
        # Pass the specific error message from the trigger/procedure
        raise ValueError(f"Failed to create issue: {err.msg}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"An unexpected error occurred creating issue: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_issue_by_id(issue_id: int) -> Optional[Issue]:
    """Retrieves a single issue by its ID, with joined data."""
    query = f"SELECT {ISSUE_COLUMNS} {ISSUE_JOINS} WHERE i.issue_id = %s"
    result = db_utils.execute_query(query, (issue_id,), fetch_one=True)

    return Issue.model_validate(result) if result else None


def get_issues_by_project_id(
    project_id: int, skip: int = 0, limit: int = 100
) -> List[Issue]:
    """Retrieves a paginated list of issues for a specific project."""
    query = f"""
        SELECT {ISSUE_COLUMNS} {ISSUE_JOINS}
        WHERE i.project_id = %s
        ORDER BY i.created_date DESC
        LIMIT %s OFFSET %s
    """
    results = db_utils.execute_query(query, (project_id, limit, skip))

    return [Issue.model_validate(row) for row in results] if results else []


def get_issues_by_sprint_id(
    sprint_id: int, skip: int = 0, limit: int = 100
) -> List[Issue]:
    """Retrieves a paginated list of issues for a specific sprint."""
    query = f"""
        SELECT {ISSUE_COLUMNS} {ISSUE_JOINS}
        WHERE i.sprint_id = %s
        ORDER BY i.priority, i.created_date DESC
        LIMIT %s OFFSET %s
    """
    results = db_utils.execute_query(query, (sprint_id, limit, skip))

    return [Issue.model_validate(row) for row in results] if results else []


def update_issue(issue_id: int, issue_in: IssueUpdate) -> Optional[Issue]:
    """
    Updates general-purpose fields on an existing issue.
    Dynamically builds the SET clause.
    Note: Status, assignee, and sprint are best updated via their dedicated endpoints.
    """
    fields_to_update = issue_in.model_dump(exclude_unset=True)

    if not fields_to_update:
        return get_issue_by_id(issue_id)

    set_clauses = []
    params = []

    # Define fields allowed for this general update
    allowed_columns = [
        "description",
        "issue_type",
        "priority",
        "due_date",
        "story_points",
        "parent_issue_id",
    ]

    for key, value in fields_to_update.items():
        if key in allowed_columns:
            set_clauses.append(f"`{key}` = %s")
            params.append(value)

    if not set_clauses:
        return get_issue_by_id(issue_id)

    params.append(issue_id)

    query = f"UPDATE Issue SET {', '.join(set_clauses)} WHERE issue_id = %s"

    try:
        db_utils.execute_query(query, tuple(params), is_commit=True)
        return get_issue_by_id(issue_id)
    except mysql.connector.Error as err:
        logger.error(f"Error updating issue {issue_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred updating issue {issue_id}: {e}")
        raise


def assign_issue_to_sprint(
    issue_id: int, assign_in: IssueAssignSprint
) -> Optional[Issue]:
    """Assigns or unassigns an issue to/from a sprint using the stored procedure."""
    query = "CALL AssignIssueToSprint(%s, %s)"
    params = (issue_id, assign_in.sprint_id)
    try:
        db_utils.execute_query(query, params, is_commit=True)
        return get_issue_by_id(issue_id)
    except mysql.connector.Error as err:
        logger.error(
            f"Error calling AssignIssueToSprint procedure for issue {issue_id}: {err}"
        )
        raise ValueError(f"Failed to assign sprint: {err.msg}")
    except Exception as e:
        logger.error(f"An unexpected error occurred assigning sprint {issue_id}: {e}")
        raise


def assign_issue_to_user(issue_id: int, assign_in: IssueAssignUser) -> Optional[Issue]:
    """Assigns or unassigns an issue to/from a user."""
    query = "UPDATE Issue SET assignee_id = %s WHERE issue_id = %s"
    params = (assign_in.assignee_id, issue_id)
    try:
        db_utils.execute_query(query, params, is_commit=True)
        return get_issue_by_id(issue_id)
    except mysql.connector.Error as err:
        logger.error(f"Error assigning user to issue {issue_id}: {err}")
        raise
    except Exception as e:
        logger.error(
            f"An unexpected error occurred assigning user to issue {issue_id}: {e}"
        )
        raise


def update_issue_status(issue_id: int, status_in: IssueUpdateStatus) -> Optional[Issue]:
    """Updates the status of an issue using the stored procedure."""
    query = "CALL UpdateIssueStatus(%s, %s)"
    params = (issue_id, status_in.status)
    try:
        db_utils.execute_query(query, params, is_commit=True)
        return get_issue_by_id(issue_id)
    except mysql.connector.Error as err:
        logger.error(
            f"Error calling UpdateIssueStatus procedure for issue {issue_id}: {err}"
        )
        raise ValueError(f"Failed to update status: {err.msg}")
    except Exception as e:
        logger.error(f"An unexpected error occurred updating status {issue_id}: {e}")
        raise


def delete_issue(issue_id: int) -> bool:
    """
    Deletes an issue from the database.
    Note: ON DELETE CASCADE/SET NULL will handle relations.
    Returns True if an issue was deleted.
    """
    query = "DELETE FROM Issue WHERE issue_id = %s"
    try:
        result = db_utils.execute_query(query, (issue_id,), is_commit=True)
        return result.get("rows_affected", 0) > 0
    except mysql.connector.Error as err:
        logger.error(f"Error deleting issue {issue_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred deleting issue {issue_id}: {e}")
        raise


def get_issue_with_details(issue_id: int) -> Optional[IssueWithDetails]:
    """
    Retrieves a single issue and all its related data:
    comments, worklogs, attachments, and total hours.
    This demonstrates aggregating data from multiple tables.
    """
    # 1. Get the base issue data (with JOINs)
    issue_data = get_issue_by_id(issue_id)
    if not issue_data:
        return None

    # 2. Get related comments
    comments = crud_comment.get_comments_by_issue_id(issue_id)

    # 3. Get related worklogs
    worklogs = crud_worklog.get_worklogs_by_issue_id(issue_id)

    # 4. Get related attachments
    attachments = crud_attachment.get_attachments_by_issue_id(issue_id)

    # 5. Get total hours logged using the SQL Function
    total_hours = crud_worklog.get_total_hours_for_issue(issue_id)

    # 6. Combine everything into the detailed model
    # We use model_dump() to convert the 'Issue' model back to a dict
    # so we can easily add the new fields for the 'IssueWithDetails' model.
    issue_details_dict = issue_data.model_dump()
    issue_details_dict.update(
        {
            "comments": comments,
            "worklogs": worklogs,
            "attachments": attachments,
            "total_hours_logged": total_hours,
        }
    )

    return IssueWithDetails.model_validate(issue_details_dict)
