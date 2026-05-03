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

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh
# Make it executable
RUN chmod +x /entrypoint.sh    

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
sys.path.insert(0, '/app')\n\
\n\
import uvloop\n\
uvloop.install()\n\
\n\
from IPython import get_ipython\n\
ipython = get_ipython()\n\
if ipython:\n\
    ipython.enable_gui = lambda gui: None\n\
\n\
from app.core.config import settings\n\
from app.db.session import get_db, async_session_maker\n\
\n\
print('='*60)\n\
print('Quittung - Async Dev Shell')\n\
print('='*60)\n\
print('Available imports:')\n\
print('  - settings: Application configuration')\n\
print('  - get_db: FastAPI DB dependency')\n\
print('  - async_session_maker: SQLAlchemy session factory')\n\
print('='*60)\n\
" > /root/.ipython/profile_default/startup/00-async-setup.py

# Set IPython as default shell
ENV SHELL=/usr/local/bin/ipython
ENV IPYTHONDIR=/root/.ipython

# Expose port
EXPOSE 8000

#LN/CRLF conversion
RUN apt-get update && apt-get install -y dos2unix && \
    dos2unix /app/pytest.ini /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]