"""
Vercel serverless function entry point for FastAPI.
Vercel will automatically detect this as a Python serverless function.
"""
import sys
import os

# Add parent directory to path so we can import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Export app for Vercel
