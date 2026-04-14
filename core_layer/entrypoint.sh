#!/bin/sh
set -e

echo "📦 DB Migration..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "📦 Create cache table..."
python manage.py createcachetable

echo "🚀 Starting Django application"
exec "$@"
