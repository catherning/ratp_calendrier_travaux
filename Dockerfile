# Multi-stage build to reduce final image size
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .

# Install Python dependencies in virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -e .

# Runtime stage
FROM python:3.12-slim

# Install only runtime Chrome dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgtk-3-0 \
    libnspr4 \
    libcurl4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    xdg-utils \
    xserver-xephyr \
    xvfb \
    python3-tk \
    python3-dev \
    && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i ./google-chrome*.deb \
    && apt-get --fix-broken install \
    && rm -rf /var/lib/apt/lists/* *.deb

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy project files (excluding large data directories via .dockerignore)
COPY data/ ../data/
COPY src/ ./src/

# Set environment variables for SeleniumBase
ENV SELENIUMBASE_HEADLESS=1
ENV SELENIUMBASE_BROWSER=chrome
ENV PYVIRTUALDISPLAY_DISPLAYFD=0

# Command to run the script
CMD ["python", "src/backend_app.py"]