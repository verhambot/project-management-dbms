import logging
from typing import List, Optional

# Import CRUD modules
import crud.issue as crud_issue
import crud.project as crud_project
import crud.sprint as crud_sprint  # Needed for sprint-based auth

# Import Dependencies
from dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, Response, status

# Import Models
from models.issue import (
    Issue,
    IssueAssignSprint,
    IssueAssignUser,
    IssueCreate,
    IssueUpdate,
    IssueUpdateStatus,
    IssueWithDetails,
)
from models.project import Project
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Authorization Helper Functions ---


async def get_project_and_check_read_access(
    project_id: int, current_user: User = Depends(get_current_active_user)
) -> Project:
    """
    Helper dependency to get a project and verify user has read access.
    Read Access = Admin or Project Owner. (In a real app, check membership)
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


async def get_issue_and_check_write_access(
    issue_id: int, current_user: User = Depends(get_current_active_user)
) -> Issue:
    """
    Helper dependency to get an issue and verify user has write access.
    Write Access = Admin, Project Owner, Reporter, or Assignee.
    """
    db_issue = crud_issue.get_issue_by_id(issue_id)
    if db_issue is None:
        logger.warning(f"Issue not found: {issue_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    project = crud_project.get_project_by_id(db_issue.project_id)
    if not project:
        # This is a server error; an issue shouldn't exist without a project
        logger.error(
            f"Orphaned issue found: {issue_id} references non-existent project {db_issue.project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Issue data is inconsistent",
        )

    if (
        current_user.role != "admin"
        and project.owner_id != current_user.user_id
        and db_issue.reporter_id != current_user.user_id
        and db_issue.assignee_id != current_user.user_id
    ):
        logger.warning(
            f"User {current_user.username} not authorized to write to issue {issue_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this issue",
        )

    return db_issue


async def get_project_for_issue_creation(
    project_id: int, current_user: User = Depends(get_current_active_user)
) -> Project:
    """Dependency for create_new_issue to handle all auth in one place."""
    return await get_project_and_check_read_access(project_id, current_user)


# --- Endpoints ---


# @router.post("/", response_model=Issue, status_code=status.HTTP_201_CREATED)
# async def create_new_issue(
#     issue_in: IssueCreate,
#     project: Project = Depends(get_project_for_issue_creation),  # Handles 404/403
#     current_user: User = Depends(get_current_active_user),
# ):
#     """
#     Creates a new issue within a project.
#     The reporter_id is automatically set to the current authenticated user.
#     """
#     logger.info(
#         f"User {current_user.username} creating issue in project: {project.project_key}"
#     )

#     # Ensure the issue's project_id matches the one in the URL/dependency
#     if issue_in.project_id != project.project_id:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Issue project_id does not match authorization.",
#         )

#     try:
#         created_issue = crud_issue.create_issue(
#             issue_in=issue_in, reporter_id=current_user.user_id
#         )
#         if not created_issue:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Could not create issue.",
#             )

#         logger.info(
#             f"Issue {created_issue.issue_id} created successfully in project {project.project_key}"
#         )
#         return created_issue

#     except ValueError as ve:
#         logger.warning(f"Failed to create issue due to validation error: {ve}")
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
#     except Exception as e:
#         logger.exception(f"An unexpected error occurred creating issue: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An internal error occurred.",
#         )


@router.post("/", response_model=Issue, status_code=status.HTTP_201_CREATED)
async def create_new_issue(
    issue_in: IssueCreate,
    # project: Project = Depends(get_project_for_issue_creation), # <-- THIS WAS THE BUG. REMOVE IT.
    current_user: User = Depends(get_current_active_user),
):
    """
    Creates a new issue within a project.
    The reporter_id is automatically set to the current authenticated user.
    """
    logger.info(
        f"User {current_user.username} creating issue in project: {issue_in.project_id}"
    )

    # --- NEW MANUAL AUTH CHECK ---
    # We validate the user's access *after* we get the issue_in body.
    try:
        # We manually call the helper function that checks if the user
        # has read access to the project they are posting to.
        await get_project_and_check_read_access(
            project_id=issue_in.project_id, current_user=current_user
        )
    except HTTPException as e:
        # Re-raise the 404 Not Found or 403 Forbidden error
        logger.warning(f"Auth check failed for create_new_issue: {e.detail}")
        raise e
    # --- END NEW CHECK ---

    try:
        # Now we can safely create the issue, passing in the
        # reporter_id from the authenticated user.
        created_issue = crud_issue.create_issue(
            issue_in=issue_in, reporter_id=current_user.user_id
        )
        if not created_issue:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create issue.",
            )

        logger.info(
            f"Issue {created_issue.issue_id} created successfully in project {issue_in.project_id}"
        )
        return created_issue

    except ValueError as ve:
        # This catches validation errors from the Stored Procedure
        logger.warning(f"Failed to create issue due to validation error: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception(f"An unexpected error occurred creating issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.get("/", response_model=List[Issue])
async def read_issues(
    project_id: Optional[int] = None,
    sprint_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves a list of issues, filtered by project_id OR sprint_id.
    One of the filters is required.
    """
    if sprint_id:
        logger.debug(
            f"User {current_user.username} fetching issues for sprint: {sprint_id}"
        )
        sprint = crud_sprint.get_sprint_by_id(sprint_id)
        if not sprint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found"
            )
        # Check access to the sprint's project
        await get_project_and_check_read_access(sprint.project_id, current_user)
        issues = crud_issue.get_issues_by_sprint_id(sprint_id, skip=skip, limit=limit)

    elif project_id:
        logger.debug(
            f"User {current_user.username} fetching issues for project: {project_id}"
        )
        # Check access to the project
        await get_project_and_check_read_access(project_id, current_user)
        issues = crud_issue.get_issues_by_project_id(project_id, skip=skip, limit=limit)

    else:
        logger.warning(
            f"User {current_user.username} attempted to fetch issues without a filter."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A filter (project_id or sprint_id) is required.",
        )

    return issues


@router.get("/{issue_id}", response_model=IssueWithDetails)
async def read_issue_by_id(
    issue_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves a specific issue by its ID, along with all comments,
    worklogs, attachments, and total hours logged.
    """
    logger.debug(
        f"User {current_user.username} fetching details for issue ID: {issue_id}"
    )

    issue_details = crud_issue.get_issue_with_details(issue_id)
    if issue_details is None:
        logger.warning(f"Issue not found: {issue_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    # Check if user has read access to this issue's project
    await get_project_and_check_read_access(issue_details.project_id, current_user)

    return issue_details


@router.put("/{issue_id}", response_model=Issue)
async def update_existing_issue(
    issue_in: IssueUpdate,
    issue: Issue = Depends(get_issue_and_check_write_access),  # Handles 404/403
):
    """
    Updates an issue's general details (description, type, priority, etc.).
    Requires write access (Admin, Owner, Reporter, Assignee).
    Does *not* update status, assignee, or sprint (use dedicated endpoints).
    """
    logger.info(f"User attempting to update issue ID: {issue.issue_id}")

    try:
        updated_issue = crud_issue.update_issue(
            issue_id=issue.issue_id, issue_in=issue_in
        )
        return updated_issue
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred updating issue {issue.issue_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{issue_id}/status", response_model=Issue)
async def update_issue_status_endpoint(
    status_in: IssueUpdateStatus,
    issue: Issue = Depends(get_issue_and_check_write_access),  # Handles 404/403
):
    """
    Updates just the status of an issue using its stored procedure.
    Requires write access (Admin, Owner, Reporter, Assignee).
    """
    logger.info(
        f"User attempting to update status for issue ID: {issue.issue_id} to {status_in.status}"
    )
    try:
        updated_issue = crud_issue.update_issue_status(
            issue_id=issue.issue_id, status_in=status_in
        )
        return updated_issue
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception(f"Error updating status for issue {issue.issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{issue_id}/assign-user", response_model=Issue)
async def assign_issue_to_user_endpoint(
    assign_in: IssueAssignUser,
    issue_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """
    Assigns or unassigns an issue to a user.
    Requires Project Read/Write access (Admin or Project Owner).
    """
    logger.info(
        f"User {current_user.username} attempting to assign user {assign_in.assignee_id} to issue {issue_id}"
    )

    issue = crud_issue.get_issue_by_id(issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    # Check for Project-level access to perform assignments
    await get_project_and_check_read_access(issue.project_id, current_user)

    try:
        updated_issue = crud_issue.assign_issue_to_user(
            issue_id=issue_id, assign_in=assign_in
        )
        return updated_issue
    except Exception as e:
        logger.exception(f"Error assigning user for issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{issue_id}/assign-sprint", response_model=Issue)
async def assign_issue_to_sprint_endpoint(
    assign_in: IssueAssignSprint,
    issue_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """
    Assigns or unassigns an issue to a sprint using its stored procedure.
    Requires Project Read/Write access (Admin or Project Owner).
    """
    logger.info(
        f"User {current_user.username} attempting to assign sprint {assign_in.sprint_id} to issue {issue_id}"
    )

    issue = crud_issue.get_issue_by_id(issue_id)
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    # Check for Project-level access to perform assignments
    await get_project_and_check_read_access(issue.project_id, current_user)

    try:
        updated_issue = crud_issue.assign_issue_to_sprint(
            issue_id=issue_id, assign_in=assign_in
        )
        return updated_issue
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception(f"Error assigning sprint for issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_issue_by_id(
    issue: Issue = Depends(get_issue_and_check_write_access),  # Handles 404/403
    current_user: User = Depends(get_current_active_user),  # Gets user for logging
):
    """
    Deletes an issue.
    Requires write access (Admin, Owner, Reporter, Assignee).
    """
    logger.info(
        f"User {current_user.username} attempting to DELETE issue ID: {issue.issue_id}"
    )

    try:
        deleted = crud_issue.delete_issue(issue.issue_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Issue not found or could not be deleted",
            )

        logger.info(
            f"Issue {issue.issue_id} deleted successfully by {current_user.username}."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred deleting issue {issue.issue_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
