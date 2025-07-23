# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install system dependencies including poppler for PDF processing
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libpoppler-cpp-dev \
    pkg-config \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for running tests
RUN groupadd -r testuser && useradd -r -g testuser testuser

# Set working directory
WORKDIR /app

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project configuration files and README
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies including dev dependencies for testing
RUN uv sync --dev --frozen

# Explicitly install test dependencies to ensure they're available
RUN uv add --dev pytest pytest-asyncio pytest-cov fakeredis

# Copy source code and tests
COPY src/ ./src/
COPY tests/ ./tests/
COPY prompts/ ./prompts/

# Create cache directory and change ownership to testuser
RUN mkdir -p /home/testuser/.cache/uv && \
    chown -R testuser:testuser /app /home/testuser

# Switch to non-root user
USER testuser

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR=/home/testuser/.cache/uv

# Default command to run tests
CMD ["uv", "run", "python", "-m", "pytest", "-v", "--cov=src", "--cov-report=term-missing", "--cov-report=html"]
