# 📊 Market Data Collection & Distribution System

A high-performance backend for collecting, storing, and querying crypto/stock OHLCV market data — augmented with a natural language interface powered by Google Gemini.

---

## ✨ Features

- **Live Data Fetching**: Pulls OHLCV candlestick data from Binance with automatic retry on rate-limits (HTTP 429) via `tenacity` exponential backoff.
- **Time-Series Storage**: Stores data in **TimescaleDB** (PostgreSQL extension) as a Hypertable, with automatic 30-day compression and 1-year data retention policies.
- **REST API with FastAPI**: Exposes two core endpoints for programmatic and natural-language querying.
- **LLM-Powered Query Parsing**: Uses **Google Gemini** (`gemini-2.5-flash`) with Structured Output to parse free-text queries (e.g., "Get BTC data for the past 3 days") into structured database parameters.
- **Strict Type Safety**: Enforced across all layers via `pydantic` models and verified by `mypy` in strict mode.

---

## 🏗️ Architecture

```
Client App
    │
    ▼
FastAPI (api/)
    ├── GET  /api/v1/market-data      → Query DB directly
    └── POST /api/v1/query-by-text   → LLM (Gemini) → Query DB
            │
            ▼
    TimescaleDB (PostgreSQL)
            ▲
            │ (background pipeline)
    Binance Fetcher (fetchers/)
```

### Unified Data Interface

Every module communicates using a single Pydantic model defined in `core/models.py`:

```python
class OHLCV(BaseModel):
    symbol: str         # e.g. "BTC/USDT"
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str      # e.g. "1h"
```

---

## 📁 Project Structure

```
.
├── api/
│   ├── main.py             # FastAPI app entry point, lifespan management
│   ├── llm.py              # Gemini API integration (lazy-loaded client)
│   └── routers/
│       └── market_data.py  # Route handlers for market data endpoints
├── core/
│   ├── models.py           # Shared OHLCV Pydantic model
│   └── schemas.py          # Request/response schemas
├── db/
│   ├── database.py         # asyncpg connection pool & query functions
│   ├── inserter.py         # Bulk insert helper
│   ├── timescale.py        # TimescaleDB client class
│   └── init.sql            # Hypertable, compression & retention setup
├── fetchers/
│   └── binance.py          # Binance OHLCV fetcher with retry logic
├── .env.example            # Environment variable template
├── pyproject.toml          # Dependencies, linting (Ruff, Black, Mypy)
└── CONTRIBUTING.md         # Coding standards for contributors & AI agents
```

---

## ⚙️ Setup

### 1. Prerequisites
- Python 3.10+
- [Docker Desktop](https://docs.docker.com/get-docker/) (for TimescaleDB)
- A [Google Gemini API Key](https://ai.google.dev/gemini-api/docs/api-key)

### 2. Clone & Install

```bash
git clone https://github.com/quang2303/MARKET-DATA-COLLECTION.git
cd MARKET-DATA-COLLECTION

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux

# Install the project in editable mode with dev tools
pip install -e .[dev]
```

### 3. Configure Environment

```bash
# Copy the example and fill in your real values
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/market_data
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Start TimescaleDB

```bash
docker run -d \
  --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=market_data \
  timescale/timescaledb:latest-pg16
```

Then apply the schema:
```bash
docker exec -i timescaledb psql -U user -d market_data < db/init.sql
```

### 5. Run the Server

```bash
uvicorn api.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive docs: `http://127.0.0.1:8000/docs`

---

## 🚀 API Reference

### `GET /api/v1/market-data`
Query OHLCV data with explicit parameters.

| Parameter    | Type   | Example                  |
|-------------|--------|--------------------------|
| `symbol`    | string | `BTC/USDT`               |
| `timeframe` | string | `1h`                     |
| `start_time`| ISO datetime | `2024-01-01T00:00:00Z` |
| `end_time`  | ISO datetime | `2024-01-02T00:00:00Z` |

**Response**: `List[OHLCV]`

---

### `POST /api/v1/query-by-text`
Query using natural language. Gemini will extract the parameters automatically.

**Request body**:
```json
{
  "text": "Give me BTC/USDT 1-hour candles for the past 3 days"
}
```

**Response**: `List[OHLCV]`

---

### `GET /health`
Basic health check.
```json
{"status": "ok"}
```

---

## 🧹 Code Quality

```bash
# Type checking
python -m mypy .

# Linting
python -m ruff check .

# Formatting
python -m black .
```

---

## 📜 License

MIT
