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
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY src/worker/pyproject.toml ./

# Remove the lock file to force a fresh resolution in the container
RUN rm -f uv.lock

# Create cache directory in /tmp (which has more space and is ephemeral)
RUN mkdir -p /tmp/uv-cache && \
    chmod 777 /tmp/uv-cache

# Remove any existing .venv directory that might have host-specific paths
RUN rm -rf .venv

# Create a new virtual environment and install dependencies
RUN python -m venv .venv && \
    . .venv/bin/activate && \
    UV_CACHE_DIR=/tmp/uv-cache uv sync

# Force reinstall packages with compiled extensions to ensure they're compiled with the system libraries
# First uninstall any existing installations
RUN UV_CACHE_DIR=/tmp/uv-cache uv pip uninstall Pillow pydantic-core pydantic pdf2image || true

# Clear any cached wheels that might be corrupted
RUN rm -rf /tmp/uv-cache/* || true

# Reinstall with proper compilation flags and no cache
RUN UV_CACHE_DIR=/tmp/uv-cache uv pip install --no-cache-dir --force-reinstall --no-binary=Pillow --no-binary=pydantic-core pydantic-core pydantic Pillow

# Install pdf2image after Pillow is properly compiled
RUN UV_CACHE_DIR=/tmp/uv-cache uv pip install --no-cache-dir pdf2image

# Verify Pillow installation
RUN uv run python -c "from PIL import Image; print('Pillow installed successfully')"

# Copy application code
COPY src/worker/ ./

# Fix shebangs in the venv - replace any shebang line that contains python with the correct path
# This must be done AFTER copying application code to ensure the fix persists
RUN for file in /app/.venv/bin/*; do \
        if [ -f "$file" ] && [ -x "$file" ] && head -1 "$file" | grep -q "^#!.*python"; then \
            sed -i '1s|^#!.*|#!/app/.venv/bin/python|' "$file"; \
        fi; \
    done

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
ENV PATH=/app/.venv/bin:/home/celery/.local/bin:$PATH

# Default command (will be overridden by docker-compose)
CMD ["/app/start_worker.sh"]
