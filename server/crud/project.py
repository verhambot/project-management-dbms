import logging
from typing import List, Optional

import mysql.connector
from database import db_utils
from models.project import Project, ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)

# --- Base Query Components ---
# We define the columns and JOIN clause here to reuse them
# This query demonstrates a JOIN as required
PROJECT_COLUMNS = """
    p.project_id, p.project_key, p.project_name, p.description,
    p.start_date, p.end_date, p.status, p.owner_id,
    p.created_at, p.updated_at,
    u.username as owner_username
"""
PROJECT_JOIN = "FROM Project p LEFT JOIN User u ON p.owner_id = u.user_id"

# Note: For 'owner_username' to be included in the response,
# you must add `owner_username: Optional[str] = None`
# to the `Project` model in `server/models/project.py`.


def create_project(project_in: ProjectCreate, owner_id: int) -> Optional[Project]:
    """
    Creates a new project by calling the CreateProject stored procedure.
    We pass the current user's ID as the owner.
    """
    query = "CALL CreateProject(%s, %s, %s, %s, @p_project_id)"
    params = (
        project_in.project_key,
        project_in.project_name,
        project_in.description,
        owner_id,  # Set owner_id from the authenticated user
    )

    conn = None
    cursor = None
    try:
        # We need a raw connection to call a procedure and get the OUT parameter
        conn = db_utils.get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Execute the procedure call
        cursor.execute(query, params)

        # Fetch the OUT parameter
        cursor.execute("SELECT @p_project_id AS project_id")
        result = cursor.fetchone()

        conn.commit()

        project_id = result.get("project_id") if result else None

        if project_id:
            return get_project_by_id(project_id)
        return None

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        if err.errno == 1062:  # Duplicate key
            logger.warning(
                f"Failed to create project. Duplicate key: {project_in.project_key}"
            )
            raise ValueError(f"Project key '{project_in.project_key}' already exists.")
        logger.error(f"Error calling CreateProject procedure: {err}")
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"An unexpected error occurred creating project: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_project_by_id(project_id: int) -> Optional[Project]:
    """Retrieves a single project by its ID, joining with User."""
    query = f"SELECT {PROJECT_COLUMNS} {PROJECT_JOIN} WHERE p.project_id = %s"
    result = db_utils.execute_query(query, (project_id,), fetch_one=True)

    # Use model_validate to parse the dictionary
    return Project.model_validate(result) if result else None


def get_project_by_key(project_key: str) -> Optional[Project]:
    """Retrieves a single project by its unique key, joining with User."""
    query = f"SELECT {PROJECT_COLUMNS} {PROJECT_JOIN} WHERE p.project_key = %s"
    result = db_utils.execute_query(query, (project_key,), fetch_one=True)

    return Project.model_validate(result) if result else None


def get_projects(skip: int = 0, limit: int = 100) -> List[Project]:
    """
    Retrieves a paginated list of all projects, joining with User.
    Demonstrates LIMIT and OFFSET.
    """
    query = f"SELECT {PROJECT_COLUMNS} {PROJECT_JOIN} ORDER BY p.created_at DESC LIMIT %s OFFSET %s"
    results = db_utils.execute_query(query, (limit, skip))

    return [Project.model_validate(row) for row in results] if results else []


def update_project(project_id: int, project_in: ProjectUpdate) -> Optional[Project]:
    """
    Updates an existing project's details.
    Dynamically builds the SET clause.
    """
    # Get fields to update, excluding any that were not set in the request
    fields_to_update = project_in.model_dump(exclude_unset=True)

    if not fields_to_update:
        return get_project_by_id(project_id)  # No changes

    set_clauses = []
    params = []

    # Allowed columns to update
    allowed_columns = [
        "project_name",
        "description",
        "start_date",
        "end_date",
        "status",
        "owner_id",
    ]

    for key, value in fields_to_update.items():
        if key in allowed_columns:
            set_clauses.append(f"`{key}` = %s")  # Use backticks for safety
            params.append(value)

    if not set_clauses:
        return get_project_by_id(project_id)  # No valid fields

    params.append(project_id)

    query = f"UPDATE Project SET {', '.join(set_clauses)} WHERE project_id = %s"

    try:
        db_utils.execute_query(query, tuple(params), is_commit=True)
        return get_project_by_id(project_id)
    except mysql.connector.Error as err:
        logger.error(f"Error updating project {project_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred updating project {project_id}: {e}")
        raise


def delete_project(project_id: int) -> bool:
    """
    Deletes a project from the database.
    Note: ON DELETE CASCADE in the schema will delete related Sprints and Issues.
    Returns True if a project was deleted.
    """
    query = "DELETE FROM Project WHERE project_id = %s"
    try:
        result = db_utils.execute_query(query, (project_id,), is_commit=True)
        return result.get("rows_affected", 0) > 0
    except mysql.connector.Error as err:
        logger.error(f"Error deleting project {project_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred deleting project {project_id}: {e}")
        raise
