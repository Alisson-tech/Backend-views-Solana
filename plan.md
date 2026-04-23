# Technical Architecture and Project Plan: High-Performance Social Media Metrics Microservice

## 1. Overview
This project serves as a highly scalable microservice built with Python, acting as a bridge between an AI Agent and various Social Media APIs (starting with YouTube, designed to scale dynamically for Instagram, TikTok, etc.). The microservice is built to process large batches of heterogeneous URLs concurrently and return a unified, normalized JSON response.

## 2. Technology Stack
- **Language**: Python 3.10+ (mandatory strict Type Hinting)
- **Web Framework**: FastAPI (high performance, asynchronous by design)
- **Validation/Schemas**: Pydantic v2 (Input/Output contracts, Data validation)
- **API Integration**: `google-api-python-client` (YouTube API integration)
- **Concurrency**: Native Python `asyncio`
- **Security**: `pydantic-settings` / `python-dotenv`

## 3. Revised Directory Structure
The architecture strongly emphasizes domain separation, particularly separating platform-specific data extraction (Adapters) from batch orchestration (Services).

```text
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app initialization and route registration
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py          # Pydantic BaseSettings for .env management
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py       # Exposes POST /api/v1/analyze for the AI Agent
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── request.py         # AI Agent -> Microservice contracts 
│   │   └── response.py        # Microservice -> AI Agent contracts
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract Base Class (SocialPlatform)
│   │   ├── factory.py         # Factory pattern to instantiate proper platform logic
│   │   └── youtube.py         # YouTube-specific asynchronous data extraction and batching
│   └── services/
│       ├── __init__.py
│       └── orchestrator.py    # Service orchestrating batching, platform routing, and asyncio
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_adapters.py   # Test adapter JSON parsing (mocked APIs)
│   │   └── test_orchestrator.py # Test routing logic
│   └── integration/
│       └── test_api.py        # Test FastAPI endpoints (TestClient / httpx.ASGITransport)
├── .env                       # Environment variables
├── .gitignore
├── requirements.txt
└── README.md
```

## 4. Asynchronous Flow Logic (Concurrency)
To provide a high-performance experience, the AI Agent interacts via a single batch request containing mixed URLs (e.g., YouTube and Instagram). The system parses this request and executes the data fetching concurrently.

1. **Routing**: The `orchestrator.py` service iterates over the input `tasks` and groups them by `platform`.
2. **Execution via `asyncio.gather`**: For each platform group, the Orchestrator delegates the work to that specific adapter's batch execution method. Tasks are executed simultaneously.

```python
import asyncio
# Example usage inside orchestrator.py
async def run_batch_analysis(tasks: List[PlatformTask], deep_analysis: bool):
    # Group tasks by platform...
    coroutines = [adapter.process_batch(platform_tasks, deep_analysis) for adapter in selected_adapters]
    
    # Wait for all adapters to finish concurrently
    results = await asyncio.gather(*coroutines)
    return flatten(results)
```

## 5. Adapter Strategy (Platform Agnosticism)
The microservice identifies the platform via the `platform` field in the request payload and dynamically routes the task using the Factory pattern.

**Abstract Base Class (`app/adapters/base.py`)**:
Every platform must abide by a strict interface to abstract the technical details away from the orchestration layer.

```python
from abc import ABC, abstractmethod
from typing import List
from app.schemas.response import VideoResult
from app.schemas.request import PlatformTask

class SocialPlatform(ABC):
    @abstractmethod
    async def process_batch(self, tasks: List[PlatformTask], deep_analysis: bool) -> List[VideoResult]:
        """
        Process a batch of URLs specific to this platform.
        """
        pass
```

## 6. YouTube Quota Optimization (Batch Processing)
To preserve the YouTube API quota and maximize speed, the `YouTubeAdapter` implements a smart batching mechanism.

- **Extraction**: When the `YouTubeAdapter` receives its list of tasks, it extracts all the YouTube Video IDs.
- **Batching**: It chunks the IDs into lists of up to 50 items (the maximum allowed by the YouTube API for the `videos().list` endpoint).
- **Quota Efficiency**: It sends one API request per 50 videos utilizing the `id` parameter (e.g. `id="id1,id2...,id50"`). This fetches the views, likes, and titles for all 50 videos in a single network roundtrip to Google servers.
- **Comment Sampling**: Comment sampling (`deep_analysis=True`) requires hitting the `commentThreads().list` endpoint. The adapter will map these individual requests into Coroutines and fire them simultaneously via `asyncio.gather`. It retrieves the top 10 relevant and bottom 10 comments to append to the results.

## 7. Security & Env Configuration
We eliminate hardcoded logic and safely manage credentials via `pydantic-settings`. 

**`.env` file**:
```env
YOUTUBE_API_KEY="your_secure_api_key"
```

**`app/core/config.py`**:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    YOUTUBE_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

## 8. Contracts & Endpoint Definition

**Input (AI Agent -> Microservice): `app/schemas/request.py`**
```python
from pydantic import BaseModel, HttpUrl
from typing import List

class PlatformTask(BaseModel):
    url: HttpUrl
    platform: str

class AnalysisBatchRequest(BaseModel):
    job_id: str
    deep_analysis: bool
    tasks: List[PlatformTask]
```

**Output (Microservice -> AI Agent): `app/schemas/response.py`**
```python
from pydantic import BaseModel
from typing import List
from datetime import datetime

class Metrics(BaseModel):
    views: int
    likes: int
    comments: int

class VideoResult(BaseModel):
    platform: str
    video_id: str
    metrics: Metrics
    comment_sample: List[str]
    normalized_at: datetime

class AnalysisBatchResponse(BaseModel):
    status: str
    job_id: str
    results: List[VideoResult]
```

## 9. Testing Strategy
Given the asynchronous nature of the microservice, the testing framework relies on **Pytest** and the `pytest-asyncio` plugin.

### Mocking Strategy
The core of our testing strategy utilizes `unittest.mock` (or `pytest-mock`) to simulate external dependencies, specifically the YouTube API interactions. **Under no circumstances should the test suite hit the real YouTube API.** This preserves quota limits and ensures tests can run completely offline.

### Coverage Goals
The test suite must explicitly validate the following key conditions:
- **Successful Extraction**: Validate data is correctly extracted and mapped to Pydantic responses using mock (static JSON) payload responses representing valid YouTube API formats.
- **Graceful Failure**: Validate safe handling and mapping when anticipated errors occur, such as a "Video Not Found" or a "Private Video". The system must not crash; instead, it should yield predictable schema validation constraints.
- **Input Validation**: Guarantee the FastAPI/Pydantic layer catches invalid AI Agent payload requests (e.g., invalid scheme for URL, missing tasks) before reaching orchestrator execution.

### Mocked YouTube Adapter Test Example (`tests/unit/test_adapters.py`)
```python
import pytest
from unittest.mock import AsyncMock, patch
from app.adapters.youtube import YouTubeAdapter
from app.schemas.request import PlatformTask

@pytest.mark.asyncio
async def test_youtube_adapter_parses_json_correctly():
    # Arrange
    tasks = [PlatformTask(url="https://youtube.com/watch?v=mock1", platform="youtube")]
    adapter = YouTubeAdapter()
    
    # Mocking YouTube API raw JSON response
    mock_response = {
        "items": [{
            "id": "mock1",
            "snippet": {"title": "Mocked Analytics Video"},
            "statistics": {"viewCount": "1000", "likeCount": "50"}
        }]
    }

    # Act
    with patch.object(adapter, '_execute_fetch', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_response
        results = await adapter.process_batch(tasks, deep_analysis=False)

    # Assert
    assert len(results) == 1
    assert results[0].video_id == "mock1"
    assert results[0].metrics.views == 1000
    assert results[0].metrics.likes == 50
```
