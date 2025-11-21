import logging
import os

import mysql.connector.pooling
from dotenv import load_dotenv

# Load environment variables from .env file
# We specify the path relative to this file's location (server/database/)
# It looks for the .env file in the 'server/' directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)

# --- Database Configuration ---
# Read connection details from environment variables
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),  # Default to 127.0.0.1 (localhost)
    "port": int(os.getenv("DB_PORT", 3307)),  # Default to 3307 (host port)
    "user": os.getenv("MYSQL_USER", "user"),
    "password": os.getenv("MYSQL_PASSWORD", "password"),
    "database": os.getenv("MYSQL_DATABASE", "jira_clone"),
}

# Global variable to hold the connection pool
connection_pool = None


async def init_db_pool():
    """
    Initializes the database connection pool.
    Called once during the FastAPI application startup (lifespan event).
    """
    global connection_pool
    if connection_pool is None:
        try:
            logger.info(
                f"Initializing database connection pool for {DB_CONFIG['host']}:{DB_CONFIG['port']}..."
            )
            connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="jira_clone_pool",
                pool_size=10,  # Adjust pool size as needed
                pool_reset_session=True,
                **DB_CONFIG,
            )
            # Try getting a connection to verify the pool is working
            conn = connection_pool.get_connection()
            if conn.is_connected():
                logger.info("Database connection pool successfully initialized.")
                conn.close()
            else:
                logger.error("Failed to establish initial connection for pool.")
                connection_pool = None
        except mysql.connector.Error as err:
            logger.error(f"Error initializing database pool: {err}")
            connection_pool = None
            # This is a critical failure, so we'll re-raise it
            raise ConnectionError(f"Failed to initialize database pool: {err}") from err
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during DB pool initialization: {e}"
            )
            connection_pool = None
            raise ConnectionError(
                f"Unexpected error initializing database pool: {e}"
            ) from e


async def close_db_pool():
    """
    Closes the database connection pool.
    Called once during the FastAPI application shutdown.

    Note: mysql-connector-python's pool doesn't have an explicit 'close' method.
    We just reset the global variable. Connections are returned to the pool
    and closed individually.
    """
    global connection_pool
    if connection_pool is not None:
        logger.info("Database pool management handled by mysql.connector.pooling.")
        # Reset the reference
        connection_pool = None


def get_db_connection():
    """
    Gets a connection from the initialized pool.
    This function will be called by CRUD operations.
    """
    if connection_pool is None:
        logger.error("Database pool is not initialized. Cannot get connection.")
        raise ConnectionError("Database pool not initialized.")
    try:
        conn = connection_pool.get_connection()
        if not conn.is_connected():
            logger.error("Failed to get a valid connection from the pool.")
            raise ConnectionError("Failed to get a valid connection from the pool.")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Error getting connection from pool: {err}")
        raise ConnectionError(f"Could not get connection from pool: {err}") from err
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting DB connection: {e}")
        raise ConnectionError(f"Unexpected error getting DB connection: {e}") from e


def execute_query(
    query: str,
    params: tuple = (None, None),
    fetch_one: bool = False,
    is_commit: bool = False,
):
    """
    Executes a given SQL query with optional parameters.
    Handles connection opening, cursor management, and connection closing.

    Args:
        query (str): The SQL query to execute.
        params (tuple, optional): Parameters to substitute into the query.
        fetch_one (bool, optional): True to fetch one result, False to fetch all.
        is_commit (bool, optional): True if the query is an INSERT, UPDATE, DELETE, or CALL to a procedure that modifies data.

    Returns:
        dict, list[dict], or dict (for commit):
        - For SELECT (fetch_one=True): A single dictionary or None.
        - For SELECT (fetch_one=False): A list of dictionaries or an empty list.
        - For COMMIT (is_commit=True): A dictionary with {'last_insert_id': id} or {'rows_affected': count}.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        # dictionary=True returns results as dictionaries (column_name: value)
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute(query, params or ())

        if is_commit:
            conn.commit()
            last_id = cursor.lastrowid
            rows_affected = cursor.rowcount
            # For procedures, lastrowid might be 0, so rowcount can be useful
            return {"last_insert_id": last_id, "rows_affected": rows_affected}

        if fetch_one:
            result = cursor.fetchone()
            return result
        else:
            result = cursor.fetchall()
            return result

    except mysql.connector.Error as err:
        logger.error(f"Database query error: {err}. Query: {query}, Params: {params}")
        if conn and is_commit:
            conn.rollback()  # Rollback transaction on error
        # Re-raise the error to be handled by the API endpoint
        raise
    except ConnectionError as conn_err:
        # Handle pool/connection specific errors
        logger.error(f"Connection Error during query execution: {conn_err}")
        raise
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during query execution: {e}. Query: {query}"
        )
        if conn and is_commit:
            conn.rollback()
        raise
    finally:
        # Ensure cursor and connection are always closed and returned to the pool
        if cursor:
            cursor.close()
        if conn:
            conn.close()
