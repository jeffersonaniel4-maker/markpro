
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Get database connection from Railway
database_url = os.getenv("DATABASE_URL")

# Use PyMySQL instead of MySQLdb
if database_url and database_url.startswith("mysql://"):
    database_url = database_url.replace(
        "mysql://", "mysql+pymysql://", 1
    )


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-only-change-this-before-deployment"
    )

    SQLALCHEMY_DATABASE_URI = database_url or (
        f"sqlite:///{PROJECT_ROOT / 'instance' / 'marks_gadgets_dev.sqlite'}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        str(PROJECT_ROOT / "uploads")
    )
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
