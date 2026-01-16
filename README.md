# Hawaii Car Rental API - Filtered Reservations

A Python FastAPI service that filters and returns only necessary data from the car rental reservations API.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and update with your credentials (if needed):
```bash
copy .env.example .env
```

## Running the API

```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### GET `/reservations`

Get filtered car rental reservations.

**Query Parameters:**
- `start_date` (required): Start date in YYYY-MM-DD format
- `end_date` (required): End date in YYYY-MM-DD format
- `status` (optional): Comma-separated statuses (e.g., "rental,completed"). Default: "rental,completed"
- `fields` (optional): Comma-separated list of fields to include in response

**Example:**
```
GET /reservations?start_date=2025-10-01&end_date=2025-12-31&status=rental,completed&fields=id,pick_up_date,return_date,status,customer.first_name,customer.last_name
```

## Next Steps

Once you provide the specific fields you need, I'll update the `filter_reservation_data` function to return only those fields by default.
