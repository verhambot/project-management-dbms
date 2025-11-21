import logging
import traceback
from contextlib import asynccontextmanager

from database import db_utils
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mysql.connector import Error as MySQLError
from routers import (
    attachments,
    auth,
    comments,
    issues,
    projects,
    sprints,
    users,
    worklogs,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan events.
    Called on startup and shutdown.
    """
    logger.info("Application startup: Initializing database connection pool...")
    try:
        await db_utils.init_db_pool()
        logger.info("Database connection pool initialized successfully.")
    except Exception as e:
        logger.critical(f"FATAL: Database pool initialization failed: {e}")

    yield

    logger.info("Application shutdown: Closing database connection pool...")
    await db_utils.close_db_pool()
    logger.info("Database connection pool closed.")


app = FastAPI(
    title="Project Management API",
    description="API for a Jira-like project management tool, built with FastAPI and MySQL.",
    version="0.1.0",
    lifespan=lifespan,
)


origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled server errors (500).
    """
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Logs standard FastAPI HTTPExceptions before returning them.
    """
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(MySQLError)
async def mysql_exception_handler(request: Request, exc: MySQLError):
    """
    Catches specific MySQL errors that might not be caught in CRUD.
    """
    logger.error(f"Database error: {exc.errno} - {exc.msg}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"A database error occurred: {exc.msg}"},
    )


app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(sprints.router, prefix="/api/sprints", tags=["Sprints"])
app.include_router(issues.router, prefix="/api/issues", tags=["Issues"])
app.include_router(comments.router, prefix="/api/comments", tags=["Comments"])
app.include_router(worklogs.router, prefix="/api/worklogs", tags=["Worklogs"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["Attachments"])


@app.get("/", tags=["Root"])
async def read_root():
    """A simple root endpoint to show the API is running."""
    return {"message": "Welcome to the Project Management API"}


@app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
async def health_check():
    """
    Checks if the API is running and can connect to the database.
    """
    conn = None
    try:
        conn = db_utils.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        logger.info("Health check successful: Database connected.")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
    finally:
        if conn:
            conn.close()
