import logging
from datetime import timedelta

import crud.user as crud_user
from config import settings  # Import the global SETTINGS instance
from core import security
from dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from models.token import Token
from models.user import User, UserCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate):
    """
    Registers a new user.
    - Checks if the username or email already exists.
    - Hashes the password.
    - Creates the user in the database.
    - Returns the new user (without the password hash).
    """
    logger.info(f"Registration attempt for username: {user_in.username}")

    # Check if user already exists
    try:
        existing_user_email = crud_user.get_user_by_email(user_in.email)
        if existing_user_email:
            logger.warning(
                f"Registration failed: Email '{user_in.email}' already registered."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        existing_user_username = crud_user.get_user_by_username(user_in.username)
        if existing_user_username:
            logger.warning(
                f"Registration failed: Username '{user_in.username}' already exists."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        # Hash the password
        hashed_password = security.get_password_hash(user_in.password)

        # Create user in DB
        created_user_db = crud_user.create_user(
            user_in=user_in, password_hash=hashed_password
        )
        if not created_user_db:
            logger.error("User creation failed in CRUD operation.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create user.",
            )

        logger.info(f"User '{user_in.username}' registered successfully.")
        # Return the 'public' User model
        return User.model_validate(created_user_db)

    except ValueError as ve:
        # Catch specific errors raised from CRUD (like duplicate entry)
        logger.warning(f"Registration failed with ValueError: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.exception(f"An unexpected error occurred during user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during registration.",
        )


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Handles user login via OAuth2 compatible form data (username & password).
    - Authenticates the user.
    - Returns a JWT access token if successful.
    """
    logger.info(f"Login attempt for username: {form_data.username}")

    # Authenticate user (checks username and verifies password)
    user = security.authenticate_user(form_data.username, form_data.password)

    if not user:
        logger.warning(
            f"Login failed for username: {form_data.username} - Invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={
            "sub": user.username,
            "user_id": user.user_id,
        },  # 'sub' is standard for 'subject'
        expires_delta=access_token_expires,
    )

    logger.info(f"Login successful for user: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Protected endpoint to get the current logged-in user's details.
    The 'get_current_active_user' dependency handles all the
    token validation and user fetching.
    """
    # The dependency already returns the correct User model
    return current_user
