from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


ENV_PATH = Path(BASE_DIR) / Path(".env")
load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3307
    MYSQL_USER: str = "user"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "jira_clone"

    JWT_SECRET_KEY: str = "default_secret_please_change"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    UPLOAD_DIRECTORY_NAME: str = "uploads"


settings = Settings()


UPLOAD_DIRECTORY_PATH = Path(BASE_DIR) / Path(settings.UPLOAD_DIRECTORY_NAME)

UPLOAD_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
