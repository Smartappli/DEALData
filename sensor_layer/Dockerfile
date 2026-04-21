# Base Python slim image
FROM python:3.14-slim

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

# Do not create .pyc files, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY ./requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY ./ ${APP_HOME}

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x ./entrypoint.sh

# User non-root
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose the port
EXPOSE 7000

ENTRYPOINT ["/entrypoint.sh"]

# Startup command: Django ASGI via granian
CMD ["granian", "sensor.asgi:application", "--interface", "asginl", "--host", "0.0.0.0", "--port", "7002", "--workers", "4"]
