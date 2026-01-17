"""
Configuration settings for the application.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
BASE_URL = "https://api-america-west.caagcrm.com/api-america-west/car-rental/reservations"
AUTH_TOKEN = os.getenv(
    "AUTH_TOKEN",
    "Basic dTAzNUhSVWRGQUdvZlFPNzg2UVdoQmJEWWVFb3A2Tjk0bUFQODk3UEhRQ1VJY2c0ZG46cmp5YUZsWGVVM2pzQURTdkV5THJEYkpNYUlwYnpJbjFDUEFnRGJHbnF2ckxsNDhuc0Q="
)

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./reservations.db")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
