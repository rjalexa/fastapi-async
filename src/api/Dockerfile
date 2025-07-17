FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# Note: Using latest available gcc version as build dependency
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY src/api/pyproject.toml ./
COPY README.md ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY src/api/ .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
