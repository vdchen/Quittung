# Quittung

Quittung is an AI-native service for automating financial accounting. The system accepts documents (PDF/IMG), extracts structured purchase data from them using Large Language Models (LLM), and provides users with analytics in Excel format and via API.

## Features

- Technology stack and rationale:
FastAPI: Main backend. Chosen over Django due to its native support for asynchronous processing, which is critical when waiting for responses from the LLM and Telegram API.

Aiogram 3.x: Bot framework. Enables the implementation of a user-friendly UI (buttons, loading indicators).

Celery + Redis: Task queue. PDF processing is a “heavy” operation. The bot must instantly respond with “Received, processing,” while the actual processing happens in the worker.

PostgreSQL + SQLAlchemy: Storage of receipt metadata, product-category relationships, and user profiles.

Google AI Studio (Gemini API): The system’s brain. Models: Gemini 2.5 Flash, Gemini 1.5 Flash-Lite. Huge context window (up to 1 million tokens) and multimodality (understands video, audio, and PDF).

Pandas: Generation of final reports. 
- User Registration with email validation
- Login with JWT token-based authentication
- Logout functionality with session management
- Password change capability
- Async architecture with uvloop
- Redis session storage
- PostgreSQL database

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with asyncpg
- **Cache/Sessions**: Redis
- **Event Loop**: uvloop (high-performance event loop)
- **Validation**: Pydantic v2
- **Authentication**: JWT (PyJWT)
- **Password Hashing**: bcrypt
- **Testing**: pytest with pytest-asyncio

## Project Structure

```
auth-api-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration settings
│   ├── dependencies.py         # Dependency injection
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── admin.py    # Admin endpoints  
│   │           ├── auth.py     # Authentication endpoints
│   │           └── users.py    # Users endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py         # Security utilities (JWT, password hashing)
│   │   └── exceptions.py       # Custom exceptions
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py             # Database base
│   │   ├── session.py          # Async database session management
│   │   └── models.py           # SQLAlchemy models
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py             # Pydantic validation schemas
│   │   └── auth.py             # Pydantic validation schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py     # Business logic layer
│   │   └── user_service.py     # Business logic layer
│   └── utils/
│       ├── __init__.py
│       └── redis_client.py     # Async Redis client
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_admin.py           # admin features tests
│   ├── test_auth.py            # Authentication tests
│   ├── test_redis_features.py  # Authentication tests
│   └── test_user_features.py   # user features tests
├── Dockerfile
├── manage.py
├── docker-compose.yml
├── requirements.txt
├── .env
├── pytest.ini
├── alembic.ini
└── README.md
```

## Password Requirements

Passwords must meet the following criteria:
- **Length**: 8-24 characters
- **Must contain**:
  - At least one digit (0-9)
  - At least one lowercase letter (a-z)
  - At least one uppercase letter (A-Z)
  - At least one special character
- **Cannot contain**: `@`, `"`, `'`, `<`, `>`

**Valid password examples**:
- `MyPass123!`
- `Secure#Pass456`
- `StrongP_ssw0rd`

## Installation

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd auth-api-service
```

2. Create `.env`:

3. Update `.env` with your configuration (especially `SECRET_KEY` for production)

4. Start all services:
```bash
docker-compose up -d
```

5. Check logs:
```bash
docker-compose logs -f api
```

The API will be available at `http://localhost:8000`

### Local Development

1. Install Python 3.11+

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up PostgreSQL and Redis locally

5. Configure `.env` file with your database and Redis URLs

6. Run the application

## API Documentation

Once the application is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication Endpoints

#### 1. Register User
**POST** `/api/v1/auth/register`

Register a new user with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "created_at": "2026-02-09T10:30:00"
}
```

#### 2. Login
**POST** `/api/v1/auth/login`

Authenticate user and receive access token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### 3. Logout
**POST** `/api/v1/auth/logout`

Logout user and invalidate session.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

#### 4. Change Password
**PUT** `/api/v1/auth/change-password`

Change the authenticated user's password.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "old_password": "SecurePass123!",
  "new_password": "NewSecurePass456#"
}
```

**Response (200 OK):**
```json
{
  "message": "Password changed successfully"
}
```

### Health Check Endpoints

#### Root
**GET** `/`

Returns basic API information.

#### Health Check
**GET** `/health`

Returns service health status.

## Testing

Run the complete test suite:

```bash
pytest tests/ -v
```

Run with coverage report:

```bash
pytest tests/ --cov=app --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

Run specific test class:
```bash
pytest tests/test_auth.py::TestRegistration -v
```

## License

MIT License - Feel free to use this project for learning or production purposes.