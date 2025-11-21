import logging
from typing import List

import crud.issue as crud_issue

# Import CRUD modules
import crud.project as crud_project
import crud.sprint as crud_sprint

# Import Dependencies
from dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, Response, status
from models.issue import Issue

# Import Models
from models.project import Project, ProjectCreate, ProjectUpdate
from models.sprint import Sprint
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_new_project(
    project_in: ProjectCreate, current_user: User = Depends(get_current_active_user)
):
    """
    Creates a new project.
    The owner_id is automatically set to the current authenticated user.
    """
    logger.info(
        f"User {current_user.username} attempting to create project: {project_in.project_key}"
    )

    # We pass the owner_id from the authenticated user
    try:
        created_project = crud_project.create_project(
            project_in=project_in, owner_id=current_user.user_id
        )
        if not created_project:
            logger.error("Project creation returned None, but no exception was caught.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create project.",
            )

        logger.info(
            f"Project '{created_project.project_key}' created successfully with ID {created_project.project_id}"
        )
        return created_project

    except ValueError as ve:
        # Catch duplicate key errors from the CRUD layer
        logger.warning(f"Failed to create project {project_in.project_key}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred creating project {project_in.project_key}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.get("/", response_model=List[Project])
async def read_all_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),  # Protect endpoint
):
    """
    Retrieves a list of all projects.
    Currently, all authenticated users can see all projects.
    """
    projects = crud_project.get_projects(skip=skip, limit=limit)
    return projects


@router.get("/{project_id}", response_model=Project)
async def read_project_by_id(
    project_id: int,
    current_user: User = Depends(get_current_active_user),  # Protect endpoint
):
    """
    Retrieves a specific project by its ID.
    """
    logger.debug(f"User {current_user.username} fetching project ID: {project_id}")
    project = crud_project.get_project_by_id(project_id)
    if project is None:
        logger.warning(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # In a more complex system, you would check membership here.
    # For now, any authenticated user can view any project.
    return project


@router.put("/{project_id}", response_model=Project)
async def update_existing_project(
    project_id: int,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Updates a project.
    Only the project owner or an admin can perform this action.
    """
    logger.info(
        f"User {current_user.username} attempting to update project ID: {project_id}"
    )
    db_project = crud_project.get_project_by_id(project_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # --- Authorization Check ---
    if current_user.role != "admin" and db_project.owner_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized to update project {project_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this project",
        )

    try:
        updated_project = crud_project.update_project(
            project_id=project_id, project_in=project_in
        )
        if updated_project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found during update",
            )
        logger.info(f"Project {project_id} updated successfully.")
        return updated_project
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred updating project {project_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_by_id(
    project_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Deletes a project.
    Only the project owner or an admin can perform this action.
    This will cascade-delete all related issues, sprints, etc.
    """
    logger.info(
        f"User {current_user.username} attempting to DELETE project ID: {project_id}"
    )
    db_project = crud_project.get_project_by_id(project_id)
    if db_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # --- Authorization Check ---
    if current_user.role != "admin" and db_project.owner_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized to DELETE project {project_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this project",
        )

    try:
        deleted = crud_project.delete_project(project_id)
        if not deleted:
            logger.warning(
                f"Project {project_id} was not found for deletion, though it existed moments ago."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or could not be deleted",
            )

        logger.info(
            f"Project {project_id} deleted successfully by {current_user.username}."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred deleting project {project_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


# --- Nested Routes ---


@router.get("/{project_id}/sprints", response_model=List[Sprint])
async def read_project_sprints(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),  # Protect endpoint
):
    """
    Retrieves all sprints associated with a specific project.
    """
    # First, check if the project exists AND the user can access it.
    # The `read_project_by_id` function handles this check and will raise
    # a 404 or 403 error if necessary.
    await read_project_by_id(
        project_id, current_user
    )  # <-- FIX: No variable assignment

    # If the above line passes, the user is authorized. Now fetch the sprints.
    sprints = crud_sprint.get_sprints_by_project_id(project_id, skip=skip, limit=limit)
    return sprints


@router.get("/{project_id}/issues", response_model=List[Issue])
async def read_project_issues(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),  # Protect endpoint
):
    """
    Retrieves all issues associated with a specific project.
    """
    # First, check if the project exists AND the user can access it.
    await read_project_by_id(
        project_id, current_user
    )  # <-- FIX: No variable assignment

    # If the above line passes, the user is authorized. Now fetch the issues.
    issues = crud_issue.get_issues_by_project_id(project_id, skip=skip, limit=limit)
    return issues
