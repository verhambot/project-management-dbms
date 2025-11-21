import logging
from typing import List

# Import CRUD modules
import crud.comment as crud_comment
import crud.issue as crud_issue
import crud.project as crud_project

# Import Dependencies
from dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, Response, status

# Import Models
from models.comment import Comment, CommentCreate, CommentUpdate
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Authorization Helper Function ---
# This helper ensures a user has read-access to an issue before they
# can read or create comments on it.
async def get_issue_and_check_read_access(
    issue_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Dependency to get an issue and verify user has read access.
    Read Access = Admin or Project Owner (or project member in a real app)
    """
    db_issue = crud_issue.get_issue_by_id(issue_id)
    if not db_issue:
        logger.warning(f"Issue not found: {issue_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
        )

    project = crud_project.get_project_by_id(db_issue.project_id)
    if not project:
        logger.error(
            f"Orphaned issue {issue_id} links to non-existent project {db_issue.project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Issue data is inconsistent",
        )

    # Authorization logic:
    if current_user.role != "admin" and project.owner_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized for project {project.project_id} (to access issue {issue_id})."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project's resources",
        )

    return db_issue


# --- Endpoints ---


@router.post("/", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def create_new_comment(
    comment_in: CommentCreate, current_user: User = Depends(get_current_active_user)
):
    """
    Creates a new comment on an issue.
    The user must have read-access to the issue's project.
    """
    logger.info(
        f"User {current_user.username} attempting to comment on issue: {comment_in.issue_id}"
    )

    # 1. Check if issue exists and user has access to it
    # We create a new "dependency" by just calling the helper function
    try:
        await get_issue_and_check_read_access(comment_in.issue_id, current_user)
    except HTTPException as e:
        # Re-raise auth/not-found errors
        raise e

    # 2. Create the comment
    try:
        created_comment = crud_comment.create_comment(
            comment_in=comment_in, user_id=current_user.user_id
        )
        if not created_comment:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create comment.",
            )

        logger.info(
            f"Comment {created_comment.comment_id} created successfully on issue {comment_in.issue_id}"
        )
        return created_comment

    except ValueError as ve:
        logger.warning(f"Failed to create comment: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception(f"An unexpected error occurred creating comment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.get("/by-issue/{issue_id}", response_model=List[Comment])
async def read_comments_for_issue(
    issue_id: int,
    skip: int = 0,
    limit: int = 100,
    # This dependency call handles auth and issue existence
    issue=Depends(get_issue_and_check_read_access),
):
    """
    Retrieves all comments for a specific issue.
    The user must have read-access to the issue's project.
    """
    logger.debug(f"Fetching comments for issue: {issue_id}")
    comments = crud_comment.get_comments_by_issue_id(issue_id, skip=skip, limit=limit)
    return comments


@router.put("/{comment_id}", response_model=Comment)
async def update_existing_comment(
    comment_id: int,
    comment_in: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Updates an existing comment.
    Only the original author of the comment or an admin can update it.
    """
    logger.info(
        f"User {current_user.username} attempting to update comment: {comment_id}"
    )

    # 1. Get the comment
    db_comment = crud_comment.get_comment_by_id(comment_id)
    if not db_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    # 2. Authorization Check
    if current_user.role != "admin" and db_comment.user_id != current_user.user_id:
        logger.warning(
            f"User {current_user.username} not authorized to update comment {comment_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this comment",
        )

    # 3. Perform the update
    try:
        updated_comment = crud_comment.update_comment(
            comment_id=comment_id, comment_in=comment_in
        )
        if updated_comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found during update",
            )
        logger.info(f"Comment {comment_id} updated successfully.")
        return updated_comment
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred updating comment {comment_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred.",
        )


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_comment(
    comment_id: int, current_user: User = Depends(get_current_active_user)
):
    """
    Deletes a comment.
    Allowed for the comment's author, the project owner, or an admin.
    """
    logger.info(
        f"User {current_user.username} attempting to DELETE comment ID: {comment_id}"
    )

    # 1. Get the comment
    db_comment = crud_comment.get_comment_by_id(comment_id)
    if not db_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    # 2. Get the issue to find the project
    db_issue = crud_issue.get_issue_by_id(db_comment.issue_id)
    if not db_issue:
        # This is a data integrity issue, but we can still allow deletion
        logger.warning(
            f"Comment {comment_id} is on a non-existent issue {db_comment.issue_id}."
        )
        # If we can't find the issue, we can't find the project owner.
        # Only allow admin or comment author to delete orphaned comments.
        if current_user.role != "admin" and db_comment.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this comment",
            )

    # 3. Get the project to find the owner
    project_owner_id = None
    if db_issue:
        project = crud_project.get_project_by_id(db_issue.project_id)
        if project:
            project_owner_id = project.owner_id

    # 4. Authorization Check
    if (
        current_user.role != "admin"
        and db_comment.user_id != current_user.user_id
        and project_owner_id != current_user.user_id
    ):
        logger.warning(
            f"User {current_user.username} not authorized to DELETE comment {comment_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this comment",
        )

    # 5. Perform the delete
    try:
        deleted = crud_comment.delete_comment(comment_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found or could not be deleted",
            )

        logger.info(
            f"Comment {comment_id} deleted successfully by {current_user.username}."
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred deleting comment {comment_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
