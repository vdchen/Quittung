# Quittung

**Quittung** is an AI-native expense-tracking service that transforms receipt photos and PDFs into structured, categorised accounting data. It accepts files via a Telegram bot (webhook-based) or directly through a REST API, processes them asynchronously with Google Gemini, and delivers results back to the user.

---

## Features

- **Multimodal AI Extraction** — Powered by **Google Gemini 2.5 Flash**; reads receipt layouts natively without traditional OCR tuning.
- **Intelligent Categorisation** — Automatically groups items (e.g. *"Bio-Milch"* → *"Dairy"*) using LLM semantic understanding.
- **Asynchronous Pipeline** — Heavy processing is offloaded to **Celery + Redis** workers; the API stays responsive at all times.
- **Robust Error Handling** — Resilient to password-protected PDFs, corrupted images, and malformed AI responses with automatic retries and user-friendly notifications.
- **Telegram Webhook** — Receives photos and PDFs via a signed webhook; duplicate receipts are detected and skipped.
- **Excel Export** — Generates multi-sheet reports with monthly breakdowns and category analytics.
- **Secure Webhook** — Every Telegram update is verified with a `X-Telegram-Bot-Api-Secret-Token` header.
- **API Security** — REST endpoints are protected by a mandatory `X-API-Key` header.
- **Rate Limiting** — Protects the API and AI infrastructure from abuse using **FastAPI-Limiter + Redis**.
- **Automated Cleanup** — Periodic background tasks (Celery Beat) automatically purge processed files older than 24h.

---

## Tech Stack

| Category | Technology |
| :--- | :--- |
| **API** | FastAPI, Uvicorn, Pydantic v2 |
| **AI** | Google Gemini 2.5 Flash (`google-genai`) |
| **Bot** | Aiogram 3.x (types + dispatcher, webhook mode) |
| **Task Queue** | Celery + Redis |
| **Database** | PostgreSQL · asyncpg · SQLAlchemy 2.0 async |
| **Migrations** | Alembic |
| **Data Export** | Pandas + OpenPyXL |
| **Containerisation** | Docker + Docker Compose |

---

## Project Structure

```
quittung/
├── app/
│   ├── api/
│   │   ├── endpoints/v1/
│   │   │   ├── api.py           # Router aggregator
│   │   │   ├── receipts.py      # POST /receipts/upload, GET status
│   │   │   ├── exports.py       # POST /exports/, GET status
│   │   │   └── telegram.py      # POST /telegram/webhook
│   │   └── deps.py              # API dependencies (API Key auth)
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (reads .env / .env.test)
│   │   ├── celery_app.py        # Celery + Redis configuration
│   │   └── logging.py           # Centralised structlog setup (JSON / console)
│   ├── db/
│   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   ├── session.py           # Async engine, session factory, get_db dependency
│   │   └── utils.py             # Auto-create database utility
│   ├── models/receipt.py        # Receipt + LineItem ORM models
│   ├── schemas/receipt.py       # Pydantic extraction schemas
│   ├── services/
│   │   ├── ai_service.py        # Gemini API call (non-blocking executor)
│   │   ├── receipt_service.py   # DB persistence + duplicate detection
│   │   ├── export_service.py    # Excel generation (Pandas + OpenPyXL)
│   │   └── notifications.py     # Telegram message formatters
│   ├── tasks/worker.py          # Celery tasks (process_receipt_task, generate_export_task, cleanup)
│   └── main.py                  # FastAPI app factory + /health endpoint
├── scripts/
│   └── set_webhook.py           # One-shot script to register the webhook with Telegram
├── migrations/                  # Alembic revisions
├── tests/
│   ├── conftest.py              # pytest-asyncio fixtures (DB, HTTP client)
│   ├── utils.py                 # Test helpers (get_url)
│   ├── test_api.py              # API endpoint tests (upload, export, auth, size limit)
│   ├── test_services.py         # DB service unit tests
│   ├── test_worker.py           # Worker task unit tests
│   ├── test_telegram.py         # Telegram webhook + handler tests
│   ├── test_integration_ai.py   # Integration tests (mocking Gemini SDK)
│   ├── test_negative.py         # Edge cases (encrypted PDFs, corrupted files)
│   ├── test_pipeline.py         # Live integration test (real Gemini call, marked integration)
│   ├── test_cleanup.py          # File cleanup task tests
│   └── test_race_conditions.py  # Duplicate detection race condition tests
├── .github/workflows/tests.yml  # CI: ruff lint + pytest (coverage ≥ 80%)
├── .pre-commit-config.yaml      # Pre-commit hooks: gitleaks, ruff, standard checks
├── docker-compose.yml           # Production services
├── docker-compose.override.yml  # Dev overrides — gitignored, create locally (see README)
├── Dockerfile
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── .env.example
```

---

## Installation & Setup

### Prerequisites

- Docker + Docker Compose
- A [Telegram Bot Token](https://core.telegram.org/bots#botfather)
- A [Google AI Studio API Key](https://aistudio.google.com/)
- A public HTTPS URL for the webhook (e.g. via [ngrok](https://ngrok.com/))

### 1 — Clone & configure

```bash
git clone <repository-url>
cd quittung
cp .env.example .env
```

Edit `.env` and fill in:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/quittung_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=<random-256-bit-string>
GOOGLE_API_KEY=<your-google-api-key>
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_WEBHOOK_SECRET=<random-secret-for-webhook-signing>
API_KEY=<your-api-key-for-rest-endpoints>
```

### 2 — Start services

```bash
docker compose up --build
```

This starts `db`, `redis`, runs `alembic upgrade head` via the `migrations` service, then starts `api` and `worker`.

### 3 — Register the webhook

In a separate terminal (while ngrok is running):

```bash
python scripts/set_webhook.py
# Enter your public HTTPS URL: https://abc123.ngrok.io
```

The script registers the URL and passes `TELEGRAM_WEBHOOK_SECRET` so Telegram signs every update.

---

## API Endpoints

> [!IMPORTANT]
> All endpoints (except `/telegram/webhook` and system checks) require a valid API Key passed via the `X-API-Key` header and are subject to **Rate Limiting** (20 requests per minute).

### Receipt Processing

| Method    | Path                                           | Description                                     |
|-----------|------------------------------------------------|-------------------------------------------------|
| `POST`    | `/api/v1/receipts/upload`                      | Upload a PDF/JPEG/PNG for async processing      |
| `GET`     | `/api/v1/receipts/upload/status/{task_id}`     | Poll the task result                            |

**Upload request** (multipart/form-data):

```
file      = <binary>
chat_id   = 12345678   (optional — enables Telegram notifications)
```

### Export

| Method    | Path                              | Description                                     |
|-----------|-----------------------------------|-------------------------------------------------|
| `POST`    | `/api/v1/exports/`                | Trigger an Excel export                         |
| `GET`     | `/api/v1/exports/status/{task_id}`| Download the finished report                    |

### Telegram Webhook

| Method    | Path                          | Description                                            |
|-----------|-------------------------------|--------------------------------------------------------|
| `POST`    | `/api/v1/telegram/webhook`    | Receives updates from Telegram (photo + document)      |

### System

| Method    | Path       | Description   |
|-----------|------------|---------------|
| `GET`     | `/health`  | Health check  |
| `GET`     | `/`        | Root status   |

---

## Running Tests

Tests use a dedicated PostgreSQL database (`quittung_test_db`). The test environment is loaded from `.env.test` automatically via **pytest-dotenv** — no manual env switching needed.

```bash
# Inside the api container
docker compose exec api pytest

# With coverage
docker compose exec api pytest --cov=app --cov-report=term-missing

# Unit tests only (skip Gemini integration)
docker compose exec api pytest -m "not integration"
```

> **Note:** `test_pipeline.py` makes real calls to the Gemini API and requires a valid `GOOGLE_API_KEY`. It is marked `integration` and skipped in CI automatically.

---

## Environment Variables Reference

|           Variable            | Required |                 Description                       |
|-------------------------------|--------- |---------------------------------------------------|
| `DATABASE_URL`                |    ✅    | asyncpg connection string                         |
| `REDIS_URL`                   |    ✅    | Redis broker/backend URL                          |
| `SECRET_KEY`                  |    ✅    | Application secret key (used for future signing)  |
| `GOOGLE_API_KEY`              |    ✅    | Gemini API key                                    |
| `TELEGRAM_BOT_TOKEN`          |    ✅    | Token from @BotFather                             |
| `TELEGRAM_WEBHOOK_SECRET`     |    ✅    | Required — signs every Telegram webhook update    |
| `API_KEY`                     |    ✅    | Secret key for REST API authentication            |
| `UPLOAD_CLEANUP_HOURS`        |    ❌    | How long to keep files in `uploads/` (default: 24)|
| `MAX_UPLOAD_SIZE_MB`          |    ❌    | Max allowed file upload size in MB (default: 10)  |
| `CORS_ORIGINS`                |    ❌    | Allowed CORS origins list (default: ["*"])        |
| `DEBUG`                       |    ❌    | Enables SQLAlchemy query logging (default: False) |
| `ENVIRONMENT`                 |    ❌    | `development` / `testing` / `production`          |

---

## Architecture Notes

### Identity & Security

- **Identity via `chat_id`**: For a Telegram-first application, `chat_id` is the natural identity anchor. When using the Telegram Bot, this ID is guaranteed by Telegram's signed webhooks.
- **Access via `API_KEY`**: While `chat_id` identifies the *owner* of a receipt, the REST API endpoints themselves are protected by a mandatory `API_KEY`. This ensures that even if an attacker knows a `chat_id`, they cannot upload receipts or trigger exports without the server's secret key.

### Robust AI Integration

The application treats the AI service as non-deterministic. We implement **deep integration testing** (mocking at the `google-genai` SDK level) to ensure our Pydantic validation handles any malformed JSON from the model. Transient AI errors (parsing issues, timeouts) are automatically retried with exponential backoff, while permanent issues (encrypted files) are reported immediately to the user.

### Celery + async

Celery workers are synchronous. Async tasks use `asyncio.run()` in production and schedule onto the existing pytest-asyncio event loop during tests. The `generate_expenses_report` call runs blocking Pandas/Excel I/O via `loop.run_in_executor()` to keep the async session from stalling.

### Duplicate detection

Receipts are deduplicated per `(telegram_id, merchant_name, total_amount, date)`. If the same receipt is sent twice, the user receives a friendly warning and no DB record is written.

---

## License
Distributed under the MIT License. See LICENSE for more information.