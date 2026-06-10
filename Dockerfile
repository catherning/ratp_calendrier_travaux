# Backend Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install standard runtime utilities and create a non-privileged user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy package metadata first
COPY pyproject.toml ./

# Create a dummy package source structure so pip can parse dependencies
RUN mkdir -p src && touch src/__init__.py

# Install dependencies only (cached until pyproject.toml changes)
RUN pip install --no-cache-dir .

# Copy your actual source code
COPY src/ ./src/

# Install the app itself (runs instantly because dependencies are cached)
RUN pip install --no-cache-dir --no-deps .

# Ensure appuser owns the application files
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Run uvicorn server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]