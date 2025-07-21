FROM python:3.12-slim

# Prevent Python from writing bytecode files (.pyc) to disk
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure Python output is sent straight to terminal without buffering
ENV PYTHONUNBUFFERED=1

# Set proper umask to avoid permission issues
ENV UMASK=0022

# Create non-root user with specific UID/GID that matches docker-compose
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} celery && \
    useradd -u ${UID} -g celery -m celery

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    procps \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY src/worker/pyproject.toml src/worker/uv.lock* ./

# Create cache directory in /tmp (which has more space and is ephemeral)
RUN mkdir -p /tmp/uv-cache && \
    chmod 777 /tmp/uv-cache

# Install dependencies using /tmp for cache
RUN UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen

# Copy application code
COPY src/worker/ ./

# Clean any existing Python bytecode cache before setting ownership
RUN find /app -name "*.pyc" -delete && \
    find /app -name "__pycache__" -type d -exec rm -rf {} + || true

# Create necessary directories and set ownership
RUN mkdir -p /app/logs /app/tmp && \
    chown -R celery:celery /app /home/celery

# Add the enhanced startup script
COPY src/worker/start_worker.sh /app/
RUN chmod +x /app/start_worker.sh && \
    chown celery:celery /app/start_worker.sh

# Switch to non-root user
USER celery

# Set environment variables for non-root operation
ENV C_FORCE_ROOT=0
ENV CELERY_WORKER_HIJACK_ROOT_LOGGER=false
ENV UV_CACHE_DIR=/tmp/uv-cache
ENV HOME=/home/celery
ENV PATH=/home/celery/.local/bin:$PATH

# Default command (will be overridden by docker-compose)
CMD ["/app/start_worker.sh"]
