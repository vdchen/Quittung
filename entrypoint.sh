#!/bin/bash
# entrypoint.sh

# Exit immediately if a command exits with a non-zero status
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting the application..."
# Execute the CMD passed from the Dockerfile
exec "$@"got 