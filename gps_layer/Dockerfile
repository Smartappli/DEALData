# Stage 1: Build with all dependencies
FROM python:3.14-slim-trixie AS builder

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

# Do not create .pyc files, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies (e.g. for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    pkg-config \
    libpq-dev \
    curl \
    ca-certificates \
 && ln -sf /usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)/libgdal.so /usr/lib/libgdal.so \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# GDAL Path
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so

# Copy and install Python dependencies
COPY ./requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --prefix=/install --no-cache-dir minio boto3 \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt \
 && find /install -name "*.pyc" -delete \
 && find /install -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Copy project code
COPY ./ ${APP_HOME}

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Export GDAL version info
RUN echo "GDAL_VERSION=$(gdal-config --version)" >> /etc/environment

# Stage 2: Lightweight runtime image
FROM python:3.14-slim-trixie AS runtime

ARG APP_HOME=/app
WORKDIR ${APP_HOME}

COPY --from=builder /install /usr/local

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    pkg-config \
    libpq-dev \
    ca-certificates \
 && ln -sf /usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)/libgdal.so /usr/lib/libgdal.so \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so

# User non-root
RUN useradd -m appuser \
    && mkdir -p /app/staticfiles /app/logs /app/static /app/media \
    && chown -R appuser:appuser /app

COPY --from=builder /app /app
COPY --from=builder /entrypoint.sh /entrypoin.sh

RUN find /app -name "*.pyc" -delete \
    && find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true \
    && find /app -name "*.git*" -exec rm -rf {} + 2>/dev/null || true

USER appuser

# Expose the port (optional but handy)
EXPOSE 7001

# Startup command: Django ASGI via granian
CMD ["granian", "gps.asgi:application", "--interface", "asginl", "--host", "0.0.0.0", "--port", "7001", "--workers", "2"]
