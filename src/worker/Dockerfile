FROM python:3.12-slim

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
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY src/worker/pyproject.toml src/worker/uv.lock* ./

# Create cache directory with proper permissions before installing
RUN mkdir -p /home/celery/.cache/uv && \
    chown -R celery:celery /home/celery/.cache

# Install dependencies as root but with cache owned by celery
RUN UV_CACHE_DIR=/home/celery/.cache/uv uv sync --frozen && \
    chown -R celery:celery /home/celery/.cache

# Copy application code
COPY src/worker/ ./

# Create necessary directories and set ownership
RUN mkdir -p /app/logs /app/tmp && \
    chown -R celery:celery /app /home/celery

# Switch to non-root user
USER celery

# Set environment variables for non-root operation
ENV C_FORCE_ROOT=0
ENV CELERY_WORKER_HIJACK_ROOT_LOGGER=false
ENV UV_CACHE_DIR=/home/celery/.cache/uv
ENV HOME=/home/celery
ENV PATH=/home/celery/.local/bin:$PATH

# Default command (will be overridden by docker-compose)
CMD ["uv", "run", "celery", "-A", "tasks", "worker", "--loglevel=info"]