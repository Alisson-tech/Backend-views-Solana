# Social Media Metrics Microservice

High-performance Python microservice that bridges an AI Agent with social media APIs. Processes batches of heterogeneous video URLs concurrently and returns unified, normalized JSON metrics.

## Tech Stack

- **Python 3.10+** with strict Type Hinting
- **FastAPI** — async web framework
- **Pydantic v2** — input/output validation
- **google-api-python-client** — YouTube Data API v3
- **asyncio** — native concurrency

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env .env.local  # Edit with your real API key

# 4. Run the server
uvicorn app.main:app --reload

# 5. Run tests
pytest tests/ -v
```

## API

### `POST /api/v1/analyze`

```json
{
  "job_id": "job-001",
  "deep_analysis": false,
  "tasks": [
    { "url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "platform": "youtube" }
  ]
}
```

### `GET /health`

Returns `{"status": "ok"}`.

## Architecture

The project uses the **Adapter pattern** for platform agnosticism and a **Factory pattern** for dynamic adapter resolution. See `plan.md` for full architecture details.
