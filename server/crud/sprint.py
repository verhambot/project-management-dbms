import logging
from typing import List, Optional

import mysql.connector
from database import db_utils
from models.sprint import Sprint, SprintCreate, SprintUpdate

logger = logging.getLogger(__name__)


def create_sprint(sprint_in: SprintCreate) -> Optional[Sprint]:
    """
    Creates a new sprint in the database.
    """
    # First, check if the project exists to satisfy the foreign key
    project = db_utils.execute_query(
        "SELECT project_id FROM Project WHERE project_id = %s",
        (sprint_in.project_id,),
        fetch_one=True,
    )
    if not project:
        logger.warning(
            f"Attempted to create sprint for non-existent project {sprint_in.project_id}"
        )
        raise ValueError(f"Project with ID {sprint_in.project_id} does not exist.")

    query = """
        INSERT INTO Sprint (project_id, sprint_name, goal, start_date, end_date, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (
        sprint_in.project_id,
        sprint_in.sprint_name,
        sprint_in.goal,
        sprint_in.start_date,
        sprint_in.end_date,
        sprint_in.status,
    )

    try:
        result = db_utils.execute_query(query, params, is_commit=True)
        sprint_id = result.get("last_insert_id")

        if sprint_id:
            return get_sprint_by_id(sprint_id)
        return None
    except mysql.connector.Error as err:
        logger.error(f"Error creating sprint for project {sprint_in.project_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred creating sprint: {e}")
        raise


def get_sprint_by_id(sprint_id: int) -> Optional[Sprint]:
    """Retrieves a single sprint by its sprint_id."""
    query = "SELECT * FROM Sprint WHERE sprint_id = %s"
    result = db_utils.execute_query(query, (sprint_id,), fetch_one=True)

    return Sprint.model_validate(result) if result else None


def get_sprints_by_project_id(
    project_id: int, skip: int = 0, limit: int = 100
) -> List[Sprint]:
    """
    Retrieves a paginated list of all sprints for a specific project.
    Demonstrates WHERE, ORDER BY, LIMIT, and OFFSET.
    """
    query = """
        SELECT * FROM Sprint
        WHERE project_id = %s
        ORDER BY start_date DESC, created_at DESC
        LIMIT %s OFFSET %s
    """
    results = db_utils.execute_query(query, (project_id, limit, skip))

    return [Sprint.model_validate(row) for row in results] if results else []


def update_sprint(sprint_id: int, sprint_in: SprintUpdate) -> Optional[Sprint]:
    """
    Updates an existing sprint's details.
    Dynamically builds the SET clause.
    """
    fields_to_update = sprint_in.model_dump(exclude_unset=True)

    if not fields_to_update:
        return get_sprint_by_id(sprint_id)  # No changes

    set_clauses = []
    params = []

    allowed_columns = ["sprint_name", "goal", "start_date", "end_date", "status"]

    for key, value in fields_to_update.items():
        if key in allowed_columns:
            set_clauses.append(f"`{key}` = %s")
            params.append(value)

    if not set_clauses:
        return get_sprint_by_id(sprint_id)  # No valid fields

    params.append(sprint_id)

    query = f"UPDATE Sprint SET {', '.join(set_clauses)} WHERE sprint_id = %s"

    try:
        db_utils.execute_query(query, tuple(params), is_commit=True)
        return get_sprint_by_id(sprint_id)
    except mysql.connector.Error as err:
        logger.error(f"Error updating sprint {sprint_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred updating sprint {sprint_id}: {e}")
        raise


def delete_sprint(sprint_id: int) -> bool:
    """
    Deletes a sprint from the database.
    Note: ON DELETE SET NULL in the schema will set Issue.sprint_id to NULL.
    Returns True if a sprint was deleted.
    """
    query = "DELETE FROM Sprint WHERE sprint_id = %s"
    try:
        result = db_utils.execute_query(query, (sprint_id,), is_commit=True)
        return result.get("rows_affected", 0) > 0
    except mysql.connector.Error as err:
        logger.error(f"Error deleting sprint {sprint_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred deleting sprint {sprint_id}: {e}")
        raise
