import logging  # <-- FIX: Import the logging module
from typing import List

import crud.user as crud_user
from dependencies import get_current_active_user  # Import the dependency
from fastapi import APIRouter, Depends, HTTPException, status

# Import the 'public' User model for responses and the UserUpdate for input
from models.user import User, UserUpdate

# --- FIX: Create the logger instance ---
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),  # Protect this endpoint
):
    """
    Retrieves a list of users.
    This endpoint is restricted to users with the 'admin' role.
    """

    # --- Authorization Check ---
    if current_user.role != "admin":
        logger.warning(
            f"User {current_user.username} (role: {current_user.role}) attempted to list all users."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this resource. Admin role required.",
        )

    logger.info(f"Admin user {current_user.username} is fetching user list.")
    users = crud_user.get_users(skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=User)
async def read_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),  # Protect this endpoint
):
    """
    Retrieves a specific user by their ID.
    Allowed only for admins or the user requesting their own data.
    """

    # --- Authorization Check ---
    if current_user.role != "admin" and current_user.user_id != user_id:
        logger.warning(
            f"User {current_user.username} attempted to access profile for user {user_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this resource",
        )

    db_user = crud_user.get_user_by_id(user_id)
    if db_user is None:
        logger.warning(
            f"User {current_user.username} requested non-existent user ID: {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # crud_user.get_user_by_id returns UserInDB, but FastAPI
    # will automatically filter it using the 'response_model=User'
    return db_user


@router.put("/me", response_model=User)
async def update_current_user(
    user_in: UserUpdate, current_user: User = Depends(get_current_active_user)
):
    """
    Updates the details for the currently authenticated user.
    This endpoint is inherently secure as it operates on the 'current_user'
    object derived from the authentication token.
    """
    try:
        updated_user = crud_user.update_user(
            user_id=current_user.user_id, user_in=user_in
        )
        if updated_user is None:
            # This might happen if the user was deleted just after token validation
            logger.error(
                f"Failed to update user {current_user.user_id} - update returned None."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        logger.info(f"User {current_user.username} updated their profile.")
        return updated_user

    except ValueError as ve:
        # Catch specific errors from CRUD, like duplicate email
        logger.warning(
            f"Failed to update user {current_user.user_id} due to bad request: {ve}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(
            f"Error updating current user {current_user.user_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user",
        )
