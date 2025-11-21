import logging
from typing import List, Optional

import mysql.connector
from database import db_utils
from models.user import UserCreate, UserInDB, UserUpdate

logger = logging.getLogger(__name__)


def create_user(user_in: UserCreate, password_hash: str) -> Optional[UserInDB]:
    """
    Creates a new user in the database.
    The password must already be hashed.
    """
    query = """
        INSERT INTO User (username, email, password_hash, first_name, last_name, phone, role)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        user_in.username,
        user_in.email,
        password_hash,
        user_in.first_name,
        user_in.last_name,
        user_in.phone,
        "user",
    )

    try:
        result = db_utils.execute_query(query, params, is_commit=True)
        user_id = result.get("last_insert_id")

        if user_id:
            return get_user_by_id(user_id)
        return None
    except mysql.connector.Error as err:
        if err.errno == 1062:  # Duplicate entry error
            logger.warning(
                f"Failed to create user. Duplicate entry: {user_in.username} / {user_in.email}"
            )
            raise ValueError(
                f"Username '{user_in.username}' or email '{user_in.email}' already exists."
            )
        logger.error(f"Error creating user: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred creating user: {e}")
        raise


def get_user_by_id(user_id: int) -> Optional[UserInDB]:
    """Retrieves a user by their user_id."""
    query = "SELECT * FROM User WHERE user_id = %s"
    result = db_utils.execute_query(query, (user_id,), fetch_one=True)

    # Use model_validate (Pydantic v2) to parse the dictionary
    return UserInDB.model_validate(result) if result else None


def get_user_by_username(username: str) -> Optional[UserInDB]:
    """Retrieves a user by their unique username."""
    query = "SELECT * FROM User WHERE username = %s"
    result = db_utils.execute_query(query, (username,), fetch_one=True)
    # Use model_validate
    return UserInDB.model_validate(result) if result else None


def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Retrieves a user by their unique email."""
    query = "SELECT * FROM User WHERE email = %s"
    result = db_utils.execute_query(query, (email,), fetch_one=True)
    # Use model_validate
    return UserInDB.model_validate(result) if result else None


def get_users(skip: int = 0, limit: int = 100) -> List[UserInDB]:
    """
    Retrieves a paginated list of all users.
    Demonstrates LIMIT and OFFSET.
    """
    query = "SELECT * FROM User ORDER BY user_id LIMIT %s OFFSET %s"
    results = db_utils.execute_query(query, (limit, skip))

    # Use model_validate in the list comprehension
    return [UserInDB.model_validate(row) for row in results] if results else []


def update_user(user_id: int, user_in: UserUpdate) -> Optional[UserInDB]:
    """
    Updates an existing user's details.
    This dynamically builds the SET clause based on fields provided in user_in.
    """
    # Get the fields that are actually set in the update model
    # exclude_unset=True is key for partial updates
    fields_to_update = user_in.model_dump(exclude_unset=True)

    if not fields_to_update:
        return get_user_by_id(user_id)  # No changes provided

    set_clauses = []
    params = []
    for key, value in fields_to_update.items():
        # Simple validation to ensure we only update allowed fields
        if key in ["email", "first_name", "last_name", "phone"]:
            set_clauses.append(f"`{key}` = %s")  # Use backticks for safety
            params.append(value)

    if not set_clauses:
        return get_user_by_id(user_id)  # No valid fields to update

    params.append(user_id)

    query = f"UPDATE User SET {', '.join(set_clauses)} WHERE user_id = %s"

    try:
        db_utils.execute_query(query, tuple(params), is_commit=True)
        return get_user_by_id(user_id)
    except mysql.connector.Error as err:
        if err.errno == 1062:  # Duplicate entry error
            logger.warning(
                f"Failed to update user {user_id}. Duplicate email: {user_in.email}"
            )
            raise ValueError(f"Email '{user_in.email}' already exists.")
        logger.error(f"Error updating user {user_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred updating user {user_id}: {e}")
        raise


def delete_user(user_id: int) -> bool:
    """
    Deletes a user from the database.
    Returns True if a user was deleted, False otherwise.
    """
    query = "DELETE FROM User WHERE user_id = %s"
    try:
        result = db_utils.execute_query(query, (user_id,), is_commit=True)
        return result.get("rows_affected", 0) > 0
    except mysql.connector.Error as err:
        logger.error(f"Error deleting user {user_id}: {err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred deleting user {user_id}: {e}")
        raise
