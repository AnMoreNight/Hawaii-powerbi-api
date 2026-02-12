"""
MongoDB connection and collection helpers.
"""
import os
import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "hawaii_rental")
MONGODB_RESERVATIONS_COLLECTION = os.getenv("MONGODB_RESERVATIONS_COLLECTION", "reservations")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable is required for MongoDB connection")

_client: Optional[AsyncIOMotorClient] = None


async def get_client() -> AsyncIOMotorClient:
    """
    Get a singleton MongoDB client instance.
    """
    global _client
    if _client is None:
        logger.info("Connecting to MongoDB...")
        _client = AsyncIOMotorClient(MONGODB_URI)
        logger.info("MongoDB client created")
    return _client


async def get_reservations_collection() -> AsyncIOMotorCollection:
    """
    Get the MongoDB collection for reservations.
    """
    client = await get_client()
    db = client[MONGODB_DB]
    return db[MONGODB_RESERVATIONS_COLLECTION]


async def close_client():
    """
    Close the MongoDB client.
    """
    global _client
    if _client is not None:
        _client.close()
        logger.info("MongoDB connection closed")
        _client = None

