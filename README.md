# Hawaii Car Rental API - Filtered Reservations

A Python FastAPI service that filters and returns only necessary data from the car rental reservations API.

## Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment (optional):**
   ```bash
   copy .env.example .env
   ```
   Edit `.env` with your settings (see [ENV_VARIABLES.md](ENV_VARIABLES.md))

### Running the API

**Method 1: Using Python**
```bash
python main.py
```

**Method 2: Using Uvicorn (with auto-reload)**
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### Verify Installation

- **API Documentation**: http://localhost:8000/docs
- **Root Endpoint**: http://localhost:8000/

### Detailed Setup Guide

For complete setup instructions, troubleshooting, and more details, see [SETUP_GUIDE.md](SETUP_GUIDE.md)

### Testing with Postman

For detailed Postman testing instructions, see [POSTMAN_TESTING_GUIDE.md](POSTMAN_TESTING_GUIDE.md)

## API Endpoints

### GET `/reservations`

Get filtered car rental reservations directly from external API.

**Query Parameters:**
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- `status` (optional): Comma-separated statuses (e.g., "rental,completed"). Default: "rental,completed"

**Example:**
```
GET /reservations?start_date=2025-10-01&end_date=2025-12-31&status=rental,completed
```

### POST `/sync`

Sync reservations from external API to local database with upsert logic.

**Query Parameters:**
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- `status` (optional): Comma-separated statuses (default: "rental,completed")

**Upsert Logic:**
- If ID exists: Updates all fields with new values (replaces existing data)
- If ID doesn't exist: Inserts new record

**Example:**
```
POST /sync?start_date=2025-10-01&end_date=2025-12-31
```

## Deployment

### Vercel Deployment

This API is configured for deployment on Vercel. See [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for complete deployment instructions.

**Quick Deploy:**
1. Push code to GitHub
2. Import project in Vercel dashboard
3. Set environment variables (MONGODB_URI, etc.)
4. Deploy!

**Note:** The API uses MongoDB (not PostgreSQL) and is configured for Vercel's serverless environment.

## Database Setup

The API uses **MongoDB** for data storage.

### Required Configuration

1. **Set up MongoDB database**:
   - Create a MongoDB Atlas account (or use existing MongoDB instance)
   - Get your connection string
   - Example: `mongodb+srv://user:password@cluster.mongodb.net/?appName=Cluster0`

2. **Configure MONGODB_URI**:
   - Create `.env` file in project root
   - Add: `MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/?appName=Cluster0`
   - Replace with your actual MongoDB connection string
   - Optional: `MONGODB_DB=hawaii_rental` (default database name)
   - Optional: `MONGODB_RESERVATIONS_COLLECTION=reservations` (default collection name)

3. **Start the API**:
   - Collections will be created automatically on first sync
   - Run: `python main.py`

### Database Operations

- **Sync data**: Use `/sync` endpoint to fetch and store reservations
- **Upsert logic**: Existing records are updated, new records are inserted

## Power BI Integration

Connect Power BI to the `/powerbi` endpoint:

- **Endpoint**: `GET /powerbi`
- **Returns**: All reservations with automatic sync of last 60 days
- **Format**: JSON stream (memory-efficient for large datasets)
- **Usage**: Use as a web data source in Power BI
