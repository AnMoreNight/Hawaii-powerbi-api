"""
Configuration settings for the application.
"""
import os
import re
import logging
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://api-america-west.caagcrm.com/api-america-west/car-rental/reservations"
AUTH_TOKEN = os.getenv(
    "AUTH_TOKEN",
    "Basic dTAzNUhSVWRGQUdvZlFPNzg2UVdoQmJEWWVFb3A2Tjk0bUFQODk3UEhRQ1VJY2c0ZG46cmp5YUZsWGVVM2pzQURTdkV5THJEYkpNYUlwYnpJbjFDUEFnRGJHbnF2ckxsNDhuc0Q="
)

# Database Configuration
# SQLite database URL - defaults to ./reservations.db if not set
# Example: DATABASE_URL=sqlite+aiosqlite:///./reservations.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./reservations.db")

# Remove quotes if present (common when copying from examples)
DATABASE_URL = DATABASE_URL.strip('"').strip("'")

# Ensure SQLite URL format is correct
if not DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    logger.warning(f"Database URL doesn't start with 'sqlite+aiosqlite:///' - using default SQLite database")
    DATABASE_URL = "sqlite+aiosqlite:///./reservations.db"

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
