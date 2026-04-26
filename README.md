# Quittung

**Quittung** is an AI-native financial intelligence service that transforms unstructured documents (PDFs and images) into structured, categorized accounting data. By leveraging Multimodal LLMs and an asynchronous event-driven architecture, it provides users with seamless expense tracking via a Telegram interface and a secure REST API.

---

## Features

* **Multimodal AI Extraction**: Powered by **Google Gemini 2.5 Flash** to "see" and interpret receipt layouts natively, eliminating the need for traditional OCR tuning.
* **Intelligent Categorization**: Automatically groups items (e.g., *"Bio-Milch"* → *"Groceries"*) using LLM semantic understanding.
* **Production-Grade Auth**: Secure registration, JWT-based authentication, session management via Redis, and **Argon2** password hashing.
* **Asynchronous Pipeline**: Heavy PDF and image processing is offloaded to **Celery + Redis** workers to ensure the Telegram bot and API remain highly responsive.
* **Dual-Interface**: Manage expenses via a **Telegram Bot** (Aiogram 3.x) or integrate directly with the **FastAPI REST API**.
* **High-Performance Execution**: Optimized asynchronous event loop using `uvloop`.

---

## Tech Stack

| Category | Technology |
| :--- | :--- |
| **Core** | FastAPI, Aiogram 3.x, uvloop |
| **AI Brain** | Google AI Studio (**Gemini 2.5 Flash**) |
| **Task Management** | Celery & Redis |
| **Database** | PostgreSQL (asyncpg & SQLAlchemy 2.0) |
| **Data Analysis** | Pandas & OpenPyXL |
| **Security** | JWT (PyJWT), Argon2 (pwdlib) |
| **Validation** | Pydantic v2 |

---

## Project Structure

```plaintext
quittung/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/      # Auth, Users, and Receipt processing
│   ├── bot/
│   │   ├── handlers/           # Telegram command/document handlers
│   │   └── middlewares/        # Auth & Logging middlewares
│   ├── core/
│   │   ├── config.py           # Settings & Env vars
│   │   ├── security.py         # JWT & Password logic
│   │   └── exceptions.py       # Global exception handling
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models
│   │   └── session.py          # Async session management
│   ├── schemas/                # Pydantic validation (DTOs)
│   ├── services/
│   │   ├── ai_service.py       # Gemini 1.5 Flash integration
│   │   ├── excel_service.py    # Pandas report generation
│   │   └── auth_service.py     # Login/Register logic
│   ├── tasks/
│   │   └── worker.py           # Celery background tasks
│   └── main.py                 # FastAPI & Bot entry point
├── migrations/                 # Alembic database migrations
├── tests/                      # Pytest suite
├── docker-compose.yml          # Container orchestration
└── README.md

## Security & Password Policy
To ensure financial data integrity, passwords must meet high-security standards:

* **Length:** 8-24 characters.
* **Must contain:** At least one digit (0-9), one lowercase (a-z), one uppercase (A-Z), and one special character.
* **Strict Restrictions:** Characters @, ", ', <, > are forbidden to prevent injection/parsing issues.

## Installation & Setup

### Using Docker (Recommended)
1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd quittung
    ```
2.  **Configure Environment:** Create a .env file based on the provided requirements:
    * TELEGRAM_BOT_TOKEN=...
    * GOOGLE_API_KEY=...
    * DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/quittung
    * REDIS_URL=redis://redis:6379/0
    * SECRET_KEY=...
3.  **Start Services:**
    ```bash
    docker-compose up -d --build
    ```

### Local Development
* Install dependencies: `pip install -r requirements.txt`
* Run Migrations: `alembic upgrade head`
* Start Workers: `celery -A app.tasks.worker worker --loglevel=info`
* Start App: `python manage.py run` (or `uvicorn app.main:app --reload`)

## API Endpoints Summary

### Authentication
* **POST /api/v1/auth/register:** Create a new account with email validation.
* **POST /api/v1/auth/login:** Exchange credentials for a JWT and Session ID.
* **POST /api/v1/auth/logout:** Invalidate the current session in Redis.

### Receipt Processing
* **POST /api/v1/receipts/upload:** Upload PDF/IMG for async processing.
* **GET /api/v1/receipts/export:** Download the consolidated Excel report.
* **GET /api/v1/receipts/history:** Retrieve a list of parsed transactions.

## Testing
Run the full suite with coverage:
```bash
pytest tests/ -v --cov=app

## License
Distributed under the MIT License. See LICENSE for more information.