#!/bin/bash
set -e

echo "========================================"
echo "  LearnVaultX — Docker Entrypoint"
echo "========================================"

# ── Wait for PostgreSQL to be ready (using Python for reliable URL parsing) ──
echo "Waiting for PostgreSQL to be ready..."

MAX_RETRIES=30
RETRY_COUNT=0

while ! python -c "
import socket, os
from urllib.parse import urlparse
url = urlparse(os.environ.get('DATABASE_URL', ''))
host = url.hostname or 'db'
port = url.port or 5432
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
s.connect((host, port))
s.close()
" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: PostgreSQL not reachable after ${MAX_RETRIES} attempts. Exiting."
        exit 1
    fi
    echo "  Attempt ${RETRY_COUNT}/${MAX_RETRIES} — PostgreSQL not ready yet, waiting 2s..."
    sleep 2
done
echo "PostgreSQL is ready!"

# ── Run Flask-Migrate database setup ────────────────────────────
echo "Running database migrations..."

# Initialize migrations folder if it doesn't exist yet
if [ ! -d "migrations" ]; then
    echo "  No migrations/ folder found — initializing Flask-Migrate..."
    flask db init
    flask db migrate -m "Initial Docker schema"
fi

# Apply all pending migrations (safe to run repeatedly)
flask db upgrade
echo "Database migrations complete!"

# ── Start the application ────────────────────────────────────────
PORT=${PORT:-5000}
echo ""
echo "========================================"
echo "  Starting LearnVaultX on port ${PORT}"
echo "========================================"

# Use Gunicorn with gthread worker (required for Flask-SocketIO threading mode)
exec gunicorn \
    --bind 0.0.0.0:${PORT} \
    --worker-class gthread \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    wsgi:application
