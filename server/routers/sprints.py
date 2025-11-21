import logging
from typing import List

import crud.issue as crud_issue
import crud.project as crud_project  # Needed to check project access

# Import CRUD modules
import crud.sprint as crud_sprint

# Import Dependencies
from dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, Response, status
from models.issue import Issue

# Import Models
from models.sprint import Sprint, SprintCreate, SprintUpdate
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=Sprint, status_code=status.HTTP_201_CREATED)
async def create_new_sprint(
    sprint_in: SprintCreate, current_user: User = Depends(get_current_active_user)
):
    """
    Creates a new sprint.
    The request body must contain the project_id this sprint belongs to.
    """
    logger.info(
        f"User {current_user.username} attempting to create sprint for project: {sprint_in.project_id}"
    )

    # --- Authorization Check ---
    # Check if the user has access to the project they're adding a sprint to.
    # We can check if they are the owner or an admin.
    # In a real app, this would be a "is_project_member" check.
    project = crud_project.get_project_by_id(sprint_in.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if current_user.role != "admin" and project.owner_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized to create sprint in project {sprint_in.project_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create sprints in this project",
        )

    try:
        created_sprint = crud_sprint.create_sprint(sprint_in=sprint_in)
        if not created_sprint:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create sprint.",
            )

        logger.info(
            f"Sprint '{sprint_in.sprint_name}' created successfully for project {sprint_in.project_id}"
        )
        return created_sprint

    except ValueError as ve:
        logger.warning(f"Failed to create sprint: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.exception(f"An unexpected error occurred creating sprint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.get("/{sprint_id}", response_model=Sprint)
async def read_sprint_by_id(
    sprint_id: int,
    current_user: User = Depends(get_current_active_user),  # Protect endpoint
):
    """
    Retrieves a specific sprint by its ID.
    """
    logger.debug(f"User {current_user.username} fetching sprint ID: {sprint_id}")
    sprint = crud_sprint.get_sprint_by_id(sprint_id)
    if sprint is None:
        logger.warning(f"Sprint not found: {sprint_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found"
        )

    # Authorization: Check if user has access to the sprint's project
    project = crud_project.get_project_by_id(sprint.project_id)
    if not project or (
        current_user.role != "admin" and project.owner_id != current_user.user_id
    ):
        # This check assumes only owner/admin. A real app would check project membership.
        logger.warning(
            f"User {current_user.username} not authorized to access sprint {sprint_id} (project {sprint.project_id})."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this resource",
        )

    return sprint


@router.put("/{sprint_id}", response_model=Sprint)
async def update_existing_sprint(
    sprint_id: int,
    sprint_in: SprintUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Updates a sprint.
    Only the project owner or an admin can perform this action.
    """
    logger.info(
        f"User {current_user.username} attempting to update sprint ID: {sprint_id}"
    )
    await read_sprint_by_id(
        sprint_id, current_user
    )  # This re-uses the auth check from get_sprint_by_id

    # read_sprint_by_id already handles 404/403, so we just proceed

    try:
        updated_sprint = crud_sprint.update_sprint(
            sprint_id=sprint_id, sprint_in=sprint_in
        )
        if updated_sprint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sprint not found during update",
            )
        logger.info(f"Sprint {sprint_id} updated successfully.")
        return updated_sprint
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred updating sprint {sprint_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.delete("/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sprint_by_id(
    sprint_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Deletes a sprint.
    Only the project owner or an admin can perform this action.
    Issues in the sprint will have their 'sprint_id' set to NULL.
    """
    logger.info(
        f"User {current_user.username} attempting to DELETE sprint ID: {sprint_id}"
    )
    await read_sprint_by_id(sprint_id, current_user)  # Re-uses auth check

    # read_sprint_by_id handles 404/403

    try:
        deleted = crud_sprint.delete_sprint(sprint_id)
        if not deleted:
            logger.warning(f"Sprint {sprint_id} was not found for deletion.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sprint not found or could not be deleted",
            )

        logger.info(
            f"Sprint {sprint_id} deleted successfully by {current_user.username}."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred deleting sprint {sprint_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


# --- Nested Routes ---


@router.get("/{sprint_id}/issues", response_model=List[Issue])
async def read_sprint_issues(
    sprint_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),  # Protect endpoint
):
    """
    Retrieves all issues associated with a specific sprint.
    """
    # First, check if the sprint exists AND the user can access it.
    await read_sprint_by_id(sprint_id, current_user)

    # If the above line passes, the user is authorized. Now fetch the issues.
    issues = crud_issue.get_issues_by_sprint_id(sprint_id, skip=skip, limit=limit)
    return issues
