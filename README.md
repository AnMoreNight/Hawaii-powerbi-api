# Hawaii Car Rental API

A FastAPI service that syncs car rental reservation data from the CAAG CRM API into MongoDB and exposes it to Power BI.

## Quick Start

### Prerequisites
- Python 3.8+
- MongoDB Atlas account

### Installation

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file based on `.env.example`:

| Variable | Required | Description |
|---|---|---|
| `AUTH_TOKEN` | Yes | Basic auth token for CAAG CRM API |
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `MONGODB_DB` | No | Database name (default: `hawaii_rental`) |
| `MONGODB_RESERVATIONS_COLLECTION` | No | Collection name (default: `reservations`) |

### Running

```bash
python main.py
# or
uvicorn main:app --reload
```

API available at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

---

## API Endpoints

### GET `/reservations`

Fetches reservations **live from the CRM API** — does not touch MongoDB.

**Query Parameters:**
| Parameter | Required | Description |
|---|---|---|
| `start_date` | Yes | Pick-up date start (YYYY-MM-DD) |
| `end_date` | Yes | Pick-up date end (YYYY-MM-DD) |
| `status` | No | Comma-separated statuses (default: `rental,completed,cancelled-paid`) |

**Example:**
```
GET /reservations?start_date=2025-01-01&end_date=2025-12-31
```

**Response:**
```json
{
  "success": true,
  "total": 150,
  "data": [ ...reservations... ]
}
```

---

### POST `/sync`

Syncs reservations from the CRM API into MongoDB. Runs the full sync pipeline:

1. Fetches `cancelled` reservation IDs for the date range
2. Fetches `rental`, `completed`, and `cancelled-paid` reservations page by page into a local buffer
3. Excludes any cancelled IDs from the buffer before upserting
4. Bulk upserts into MongoDB in batches of 500 (upsert: update if exists, insert if new)
5. Deletes cancelled IDs from MongoDB (removes previously-synced records that later became cancelled)

**Query Parameters:**
| Parameter | Required | Description |
|---|---|---|
| `start_date` | Yes | Pick-up date start (YYYY-MM-DD) |
| `end_date` | Yes | Pick-up date end (YYYY-MM-DD) |
| `status` | No | Comma-separated statuses (default: `rental,completed,cancelled-paid`) |

**Example:**
```
POST /sync?start_date=2025-01-01&end_date=2025-12-31
```

**Response:**
```json
{
  "success": true,
  "message": "Sync completed successfully",
  "total_processed": 17072,
  "inserted": 12,
  "updated": 17060,
  "deleted": 3,
  "errors": 0
}
```

**Status handling:**

| Status | Behavior |
|---|---|
| `rental` | Upserted into MongoDB |
| `completed` | Upserted into MongoDB |
| `cancelled-paid` | Upserted into MongoDB (treated as a completed rental) |
| `cancelled` | IDs fetched separately — skipped from upsert, deleted from MongoDB |

---

### GET `/powerbi`

Primary endpoint for Power BI. Automatically syncs the **last 60 days** before returning all data.

- Uses a **5-minute sync cache** — if called multiple times within 5 minutes, skips re-syncing and returns existing data directly
- Streams results as JSON to avoid memory issues with large datasets
- Returns all reservations currently stored in MongoDB

**Example:**
```
GET /powerbi
```

**Response (streamed JSON):**
```json
{
  "success": true,
  "total": 25000,
  "data": [ ...all reservations... ]
}
```

---

## MongoDB Document Structure

```json
{
  "id": 12,
  "status": "completed",
  "pick_up_date": "2025-05-03 10:23:00.000000",
  "pick_up_location_label": "Uluniu Avenue",
  "total_days": 3,
  "total_price": 87.2,
  "discounts_amount": 0,
  "rental_user_name": "Nathan Bingham",
  "active_vehicle_information": {
    "vehicle_class_label": "Sport"
  },
  "additional_charge_category_1": "25.0000000",
  "additional_charge_category_2": "0.0000000",
  "additional_charge_category_3": "5.0000000",
  "additional_charge_category_4": "0.0000000",
  "created_at": "2026-01-23 02:39:57.601707",
  "updated_at": "2026-01-23 02:39:57.601709"
}
```

**Field notes:**
- `rental_user_name` — resolved from `rental_user_id` via the CRM's available-agents API
- `additional_charge_category_1~4` — summed from `all_additional_charges` array by `category_id`
- `created_at` — set on first insert, never overwritten
- `updated_at` — refreshed on every sync

---

## External API

**Base URL:** `https://api-america-west.caagcrm.com/api-america-west/car-rental/reservations`

**Auth:** `Authorization: Basic <AUTH_TOKEN>`

**Pagination:** Results are paginated. The sync fetches page by page until `current_page >= last_page`.

**Agents endpoint:** `GET /reservations/available-agents` — fetched once per sync to map `rental_user_id` → `full_name`.
