import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import crud.user as crud_user
from config import settings
from jose import JWTError, jwt
from models.user import UserInDB
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    Returns True if they match, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password.
    Returns the hashed password.
    """
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise ValueError("Could not hash password") from e


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Creates a new JWT access token.

    Args:
        data (Dict[str, Any]): The data to encode in the token (e.g., {'sub': username, 'user_id': id})
        expires_delta (Optional[timedelta]): Optional lifetime for the token.

    Returns:
        str: The encoded JWT string.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        logger.error(f"Error encoding JWT: {e}")
        raise ValueError("Could not create access token") from e


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """
    Authenticates a user by username and password.

    1. Fetches the user from the DB by username.
    2. Verifies the provided password against the stored hash.

    Returns:
        Optional[UserInDB]: The user object (including hashed password) if successful, else None.
    """
    logger.debug(f"Attempting to authenticate user: {username}")

    user = crud_user.get_user_by_username(username)

    if not user:
        logger.warning(f"Authentication failed: User '{username}' not found.")
        return None

    if not verify_password(password, user.password_hash):
        logger.warning(
            f"Authentication failed: Incorrect password for user '{username}'."
        )
        return None

    logger.info(f"Authentication successful for user '{username}'.")
    return user
