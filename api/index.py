"""
Vercel serverless function entry point for FastAPI.
This file is required by Vercel to handle all API routes.
"""
from main import app

# Export the app for Vercel
__all__ = ["app"]
