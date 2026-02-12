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

# MongoDB Configuration
# Example:
#   MONGODB_URI=mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
#   MONGODB_DB=hawaii_rental
#   MONGODB_RESERVATIONS_COLLECTION=reservations
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    logger.warning("MONGODB_URI is not set. Please configure it in your environment for MongoDB.")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
