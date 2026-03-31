FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create IPython profile for async support
RUN ipython profile create && \
    mkdir -p /root/.ipython/profile_default/startup

# Configure IPython for async and project imports
RUN echo "import asyncio\n\
import sys\n\
from pathlib import Path\n\
\n\
# Add app to path\n\
sys.path.insert(0, '/app')\n\
\n\
# Configure async loop\n\
import uvloop\n\
uvloop.install()\n\
\n\
# Enable top-level await\n\
from IPython import get_ipython\n\
ipython = get_ipython()\n\
if ipython:\n\
    ipython.enable_gui = lambda gui: None\n\
\n\
# Import common modules\n\
from app.config import settings\n\
from app.db.session import get_async_session\n\
from app.utils.redis_client import get_redis_client\n\
\n\
print('='*60)\n\
print('Auth API Service - Async Shell')\n\
print('='*60)\n\
print('Available imports:')\n\
print('  - settings: Configuration')\n\
print('  - get_async_session: Database session')\n\
print('  - get_redis_client: Redis client')\n\
print('='*60)\n\
" > /root/.ipython/profile_default/startup/00-async-setup.py

# Set IPython as default shell
ENV SHELL=/usr/local/bin/ipython
ENV IPYTHONDIR=/root/.ipython

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]