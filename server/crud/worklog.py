import logging
from typing import Any, Dict, List, Optional, cast

import mysql.connector
from database import db_utils
from models.worklog import Worklog, WorklogCreate, WorklogUpdate

logger = logging.getLogger(__name__)

# --- Base Query Components ---
WORKLOG_COLUMNS = """
    w.worklog_id, w.issue_id, w.user_id, w.hours_logged,
    w.work_date, w.description, w.created_at,
    u.username as logger_username
"""
WORKLOG_JOIN = """
    FROM Worklog w
    LEFT JOIN User u ON w.user_id = u.user_id
"""

# Note: For 'logger_username' to be included in the response,
# you must add `logger_username: Optional[str] = None`
# to the `Worklog` model in `server/models/worklog.py`.


def create_worklog(worklog_in: WorklogCreate, user_id: int) -> Optional[Worklog]:
    """
    Logs work on an issue using the LogWork stored procedure.
    """
    query = "CALL LogWork(%s, %s, %s, %s, %s, @p_worklog_id)"
    params = (
        worklog_in.issue_id,
        user_id,
        worklog_in.hours_logged,
        worklog_in.work_date,
        worklog_in.description,
    )

    conn = None
    cursor = None
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(query, params)

        # Fetch the OUT parameter
        cursor.execute("SELECT @p_worklog_id AS worklog_id")
        result = cursor.fetchone()

        conn.commit()

        worklog_id = result.get("worklog_id") if result else None

        if worklog_id:
            # The after_worklog_insert trigger handles updating Issue.updated_date
            return get_worklog_by_id(worklog_id)
        return None

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        logger.error(f"Error calling LogWork procedure: {err}")
        if err.errno == 1452:  # Foreign key constraint (issue not found)
            raise ValueError(f"Issue with ID {worklog_in.issue_id} not found.")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"An unexpected error occurred logging work: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_worklog_by_id(worklog_id: int) -> Optional[Worklog]:
    """Retrieves a single worklog entry by its ID, joining with User."""
    query = f"SELECT {WORKLOG_COLUMNS} {WORKLOG_JOIN} WHERE w.worklog_id = %s"
    result = db_utils.execute_query(query, (worklog_id,), fetch_one=True)

    return Worklog.model_validate(result) if result else None


def get_worklogs_by_issue_id(
    issue_id: int, skip: int = 0, limit: int = 100
) -> List[Worklog]:
    """
    Retrieves a paginated list of all worklogs for a specific issue.
    This function was required by crud/issue.py.
    """
    query = f"""
        SELECT {WORKLOG_COLUMNS} {WORKLOG_JOIN}
        WHERE w.issue_id = %s
        ORDER BY w.work_date DESC, w.created_at DESC
        LIMIT %s OFFSET %s
    """
    results = db_utils.execute_query(query, (issue_id, limit, skip))

    # Ensure results is a list before list comprehension
    if isinstance(results, list):
        return [Worklog.model_validate(row) for row in results]
    return []


def update_worklog(worklog_id: int, worklog_in: WorklogUpdate) -> Optional[Worklog]:
    """
    Updates an existing worklog entry.
    """
    fields_to_update = worklog_in.model_dump(exclude_unset=True)

    if not fields_to_update:
        return get_worklog_by_id(worklog_id)

    set_clauses = []
    params = []

    allowed_columns = ["hours_logged", "work_date", "description"]

    for key, value in fields_to_update.items():
        if key in allowed_columns:
            set_clauses.append(f"`{key}` = %s")
            params.append(value)

    if not set_clauses:
        return get_worklog_by_id(worklog_id)

    params.append(worklog_id)

    query = f"UPDATE Worklog SET {', '.join(set_clauses)} WHERE worklog_id = %s"

    try:
        db_utils.execute_query(query, tuple(params), is_commit=True)
        # Note: We might need a trigger ON UPDATE for Worklog
        # if we want Issue.updated_date to change here.
        return get_worklog_by_id(worklog_id)
    except mysql.connector.Error as err:
        logger.error(f"Error updating worklog {worklog_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred updating worklog {worklog_id}: {e}")
        raise


def delete_worklog(worklog_id: int) -> bool:
    """
    Deletes a worklog entry from the database.
    Returns True if an entry was deleted.
    """
    query = "DELETE FROM Worklog WHERE worklog_id = %s"
    try:
        result = db_utils.execute_query(query, (worklog_id,), is_commit=True)
        return result.get("rows_affected", 0) > 0
    except mysql.connector.Error as err:
        logger.error(f"Error deleting worklog {worklog_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred deleting worklog {worklog_id}: {e}")
        raise


# --- SQL Function & Aggregate Query Functions ---


def get_total_hours_for_issue(issue_id: int) -> float:
    """
    Gets total hours logged for an issue by calling the SQL function.
    This function was required by crud/issue.py.
    Demonstrates calling a SQL Function.
    """
    query = "SELECT CalculateTotalIssueHours(%s) AS total_hours"
    try:
        result = db_utils.execute_query(query, (issue_id,), fetch_one=True)
        # Ensure result is a dict and key exists before processing
        if isinstance(result, dict) and result.get("total_hours") is not None:
            # The function returns a DECIMAL, which mysql-connector returns as Decimal object
            return float(result["total_hours"])
        return 0.0
    except Exception as e:
        logger.error(
            f"Error calling CalculateTotalIssueHours function for issue {issue_id}: {e}"
        )
        return 0.0


def get_total_hours_for_project(project_id: int) -> float:
    """
    Gets total hours logged for all issues in a project.
    Demonstrates an AGGREGATE (SUM) query with a JOIN.
    """
    query = """
        SELECT SUM(w.hours_logged) as total_project_hours
        FROM Worklog w
        JOIN Issue i ON w.issue_id = i.issue_id
        WHERE i.project_id = %s
    """
    try:
        result = db_utils.execute_query(query, (project_id,), fetch_one=True)
        # Ensure result is a dict and key exists before processing
        if isinstance(result, dict) and result.get("total_project_hours") is not None:
            return float(result["total_project_hours"])
        return 0.0
    except Exception as e:
        logger.error(f"Error getting total project hours for project {project_id}: {e}")
        return 0.0


def get_total_hours_per_user_for_project(project_id: int) -> List[Dict[str, Any]]:
    """
    Gets total hours logged per user for a project.
    Demonstrates AGGREGATE (SUM), JOIN, and GROUP BY.
    """
    query = """
        SELECT
            w.user_id,
            u.username,
            SUM(w.hours_logged) as total_user_hours
        FROM Worklog w
        JOIN User u ON w.user_id = u.user_id
        JOIN Issue i ON w.issue_id = i.issue_id
        WHERE i.project_id = %s
        GROUP BY w.user_id, u.username
        ORDER BY total_user_hours DESC
    """
    try:
        query_results = db_utils.execute_query(query, (project_id,))

        # --- FIX for Type Error ---
        # 1. Check if the result is a list, as expected from fetch_one=False
        if not isinstance(query_results, list):
            logger.warning(
                f"Expected list from query, got {type(query_results)}. Project: {project_id}"
            )
            return []

        # 2. Cast for the static type checker's benefit
        results = cast(List[Dict[str, Any]], query_results)

        # 3. Process the list (which might be empty)
        for row in results:
            # Now the linter knows 'row' is a dict and can be keyed with a string
            if "total_user_hours" in row and row["total_user_hours"] is not None:
                row["total_user_hours"] = float(row["total_user_hours"])
            else:
                row["total_user_hours"] = 0.0

        return results
        # --- END FIX ---

    except Exception as e:
        logger.error(f"Error getting user hours for project {project_id}: {e}")
        return []
