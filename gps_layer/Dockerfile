# Stage 1: Build with all dependencies
FROM python:3.14-slim-trixie AS builder

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

# Do not create .pyc files, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    libpq-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy and install Python dependencies
COPY ./requirements.lock ./
RUN pip install --prefix=/install --no-cache-dir --require-hashes --only-binary :all: -r requirements.lock \
 && find /install -name "*.pyc" -delete \
 && find /install -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Stage 2: Lightweight runtime image
FROM python:3.14-slim-trixie AS runtime

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

COPY --from=builder /install /usr/local

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpq-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
 && useradd -m appuser \
 && mkdir -p /app/staticfiles /app/logs /app/static /app/media \
 && chown -R appuser:appuser /app

# Copy only application files needed at runtime.
COPY ./manage.py ./manage.py
COPY ./__init__.py ./__init__.py
COPY ./gps/*.py ./gps/
COPY ./gps_data/*.py ./gps_data/
COPY ./gps_data/management/*.py ./gps_data/management/
COPY ./gps_data/management/commands/*.py ./gps_data/management/commands/
COPY ./gps_data/migrations/*.py ./gps_data/migrations/
COPY ./entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && chown appuser:appuser /entrypoint.sh \
    && find /app -name "*.pyc" -delete \
    && find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /app -name "*.git*" -exec rm -rf {} + 2>/dev/null || true

USER appuser

# Expose the port (optional but handy)
EXPOSE 7001

ENTRYPOINT ["/entrypoint.sh"]

# Startup command: Django ASGI via granian
CMD ["granian", "gps.asgi:application", "--interface", "asgi", "--host", "0.0.0.0", "--port", "7001", "--workers", "2"]
