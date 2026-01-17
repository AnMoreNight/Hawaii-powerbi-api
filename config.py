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
# Must be set in .env file or environment variable
# Example: DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxxxx.supabase.co:5432/postgres
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Please set it in .env file or environment variables. "
        "Example: DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxxxx.supabase.co:5432/postgres"
    )

# Remove quotes if present (common when copying from examples)
DATABASE_URL = DATABASE_URL.strip('"').strip("'")

# URL-encode special characters in password if needed
# Check if password contains @ and needs encoding
import re
from urllib.parse import quote, unquote

# Extract password from connection string and encode if needed
# Format: postgresql+asyncpg://user:password@host:port/db
match = re.match(r'(postgresql\+asyncpg://[^:]+:)([^@]+)(@.+)', DATABASE_URL)
if match:
    prefix, password, suffix = match.groups()
    # If password contains @ but isn't already encoded, encode it
    if '@' in password and '%40' not in password:
        encoded_password = quote(password, safe='')
        DATABASE_URL = f"{prefix}{encoded_password}{suffix}"
        logger = logging.getLogger(__name__)
        logger.info("Password contains '@' - automatically URL-encoded")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
