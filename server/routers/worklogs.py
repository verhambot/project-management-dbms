import logging
from typing import Any, Dict, List

import crud.issue as crud_issue
import crud.project as crud_project

# Import CRUD modules
import crud.worklog as crud_worklog

# Import Dependencies
from dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, Response, status
from models.project import Project
from models.user import User

# Import Models
from models.worklog import Worklog, WorklogCreate, WorklogUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Authorization Helper Functions ---


async def get_project_and_check_read_access(
    project_id: int, current_user: User = Depends(get_current_active_user)
) -> Project:
    """
    Helper to get a project and verify user has read access.
    Read Access = Admin or Project Owner.
    """
    project = crud_project.get_project_by_id(project_id)
    if not project:
        logger.warning(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if current_user.role != "admin" and project.owner_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized for project {project_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project",
        )

    return project


async def get_issue_and_check_read_access(issue_id: int, current_user: User):
    """
    Dependency to get an issue and verify user has read access.
    """
    db_issue = crud_issue.get_issue_by_id(issue_id)
    if not db_issue:
        logger.warning(f"Issue not found: {issue_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    await get_project_and_check_read_access(db_issue.project_id, current_user)

    return db_issue


# --- Endpoints ---


@router.post("/", response_model=Worklog, status_code=status.HTTP_201_CREATED)
async def create_new_worklog(
    worklog_in: WorklogCreate, current_user: User = Depends(get_current_active_user)
):
    """
    Creates a new worklog (time entry) for an issue.
    The user must have read-access to the issue's project.
    """
    logger.info(
        f"User {current_user.username} attempting to log work for issue: {worklog_in.issue_id}"
    )

    # 1. Check if issue exists and user has access to it
    try:
        await get_issue_and_check_read_access(worklog_in.issue_id, current_user)
    except HTTPException as e:
        raise e  # Re-raise auth/not-found errors

    # 2. Create the worklog
    try:
        created_worklog = crud_worklog.create_worklog(
            worklog_in=worklog_in, user_id=current_user.user_id
        )
        if not created_worklog:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create worklog.",
            )

        logger.info(
            f"Worklog {created_worklog.worklog_id} created successfully for issue {worklog_in.issue_id}"
        )
        return created_worklog

    except ValueError as ve:
        logger.warning(f"Failed to create worklog: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception(f"An unexpected error occurred creating worklog: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.get("/by-issue/{issue_id}", response_model=List[Worklog])
async def read_worklogs_for_issue(
    issue_id: int,
    skip: int = 0,
    limit: int = 100,
    # This dependency call handles auth and issue existence
    issue=Depends(get_issue_and_check_read_access),
):
    """
    Retrieves all worklogs for a specific issue.
    The user must have read-access to the issue's project.
    """
    logger.debug(f"Fetching worklogs for issue: {issue_id}")
    worklogs = crud_worklog.get_worklogs_by_issue_id(issue_id, skip=skip, limit=limit)
    return worklogs


@router.put("/{worklog_id}", response_model=Worklog)
async def update_existing_worklog(
    worklog_id: int,
    worklog_in: WorklogUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Updates an existing worklog.
    Only the original author of the worklog or an admin can update it.
    """
    logger.info(
        f"User {current_user.username} attempting to update worklog: {worklog_id}"
    )

    # 1. Get the worklog
    db_worklog = crud_worklog.get_worklog_by_id(worklog_id)
    if not db_worklog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Worklog not found"
        )

    # 2. Authorization Check
    if current_user.role != "admin" and db_worklog.user_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized to update worklog {worklog_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this worklog",
        )

    # 3. Perform the update
    try:
        updated_worklog = crud_worklog.update_worklog(
            worklog_id=worklog_id, worklog_in=worklog_in
        )
        if updated_worklog is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worklog not found during update",
            )
        logger.info(f"Worklog {worklog_id} updated successfully.")
        return updated_worklog
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred updating worklog {worklog_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.delete("/{worklog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_worklog(
    worklog_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Deletes a worklog.
    Allowed for the worklog's author, the project owner, or an admin.
    """
    logger.info(
        f"User {current_user.username} attempting to DELETE worklog ID: {worklog_id}"
    )

    # 1. Get the worklog
    db_worklog = crud_worklog.get_worklog_by_id(worklog_id)
    if not db_worklog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Worklog not found"
        )

    # 2. Get the issue to find the project
    db_issue = crud_issue.get_issue_by_id(db_worklog.issue_id)
    project_owner_id = None
    if db_issue:
        project = crud_project.get_project_by_id(db_issue.project_id)
        if project:
            project_owner_id = project.owner_id
    else:
        logger.warning(
            f"Worklog {worklog_id} is on a non-existent issue {db_worklog.issue_id}."
        )
        # If we can't find the project owner, only allow admin or author
        if current_user.role != "admin" and db_worklog.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this worklog",
            )

    # 3. Authorization Check
    if (
        current_user.role != "admin"
        and db_worklog.user_id != current_user.user_id
        and project_owner_id != current_user.user_id
    ):
        logger.warning(
            f"User {current_user.username} not authorized to DELETE worklog {worklog_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this worklog",
        )

    # 4. Perform the delete
    try:
        deleted = crud_worklog.delete_worklog(worklog_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worklog not found or could not be deleted",
            )

        logger.info(
            f"Worklog {worklog_id} deleted successfully by {current_user.username}."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred deleting worklog {worklog_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Aggregate Endpoints ---


@router.get("/by-issue/{issue_id}/total-hours", response_model=Dict[str, float])
async def get_total_hours_for_issue_endpoint(
    issue_id: int, issue=Depends(get_issue_and_check_read_access)  # Handles auth
):
    """
    Gets the total hours logged for a single issue by calling the SQL function.
    """
    logger.debug(f"Fetching total hours for issue: {issue_id}")
    total_hours = crud_worklog.get_total_hours_for_issue(issue_id)
    return {"issue_id": issue_id, "total_hours_logged": total_hours}


@router.get("/by-project/{project_id}/total-hours", response_model=Dict[str, float])
async def get_total_hours_for_project_endpoint(
    project_id: int, project=Depends(get_project_and_check_read_access)  # Handles auth
):
    """
    Gets the total hours logged for all issues in a project.
    """
    logger.debug(f"Fetching total hours for project: {project_id}")
    total_hours = crud_worklog.get_total_hours_for_project(project_id)
    return {"project_id": project_id, "total_project_hours": total_hours}


@router.get(
    "/by-project/{project_id}/hours-by-user", response_model=List[Dict[str, Any]]
)
async def get_project_hours_by_user_endpoint(
    project_id: int, project=Depends(get_project_and_check_read_access)  # Handles auth
):
    """
    Gets a report of total hours logged per user for a specific project.
    Demonstrates an aggregate query with GROUP BY.
    """
    logger.debug(f"Fetching hours-by-user report for project: {project_id}")
    report = crud_worklog.get_total_hours_per_user_for_project(project_id)
    return report
