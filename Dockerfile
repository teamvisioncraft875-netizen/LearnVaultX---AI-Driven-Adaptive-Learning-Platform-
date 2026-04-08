# ─── LearnVaultX Dockerfile ──────────────────────────────────────
# Production-ready, lightweight Python 3.10 image
# ─────────────────────────────────────────────────────────────────

FROM python:3.10-slim

# Prevent Python from buffering stdout/stderr (important for Docker logs)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies required by psycopg2 and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (layer caching optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Create the uploads directory inside the container
RUN mkdir -p /app/instance/uploads

# Make the entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Expose the application port
EXPOSE 5000

# Use the entrypoint script to handle migrations + startup
ENTRYPOINT ["/app/docker-entrypoint.sh"]
