import logging
from typing import Optional

import crud.user as crud_user
from config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from models.user import User
from pydantic import ValidationError

logger = logging.getLogger(__name__)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        user_id: Optional[int] = payload.get("user_id")

        if user_id is None:
            logger.warning("Token payload is missing 'user_id'")
            raise credentials_exception

    except (JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise credentials_exception from e

    user = crud_user.get_user_by_id(user_id=user_id)

    if user is None:

        logger.warning(f"User ID {user_id} from token not found in DB")
        raise credentials_exception

    return User.model_validate(user)


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    A dependency that builds on get_current_user.

    We can add logic here to check if the user is active,
    banned, etc., based on fields in the User model.
    For now, it just returns the user.
    """
    # Example for the future:
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")

    return current_user
