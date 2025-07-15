#!/bin/sh

echo "Waiting for PostgreSQL to start..."
while ! pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -q; do
  sleep 2
done
echo "PostgreSQL started"

echo "Applying database migrations..."
python manage.py migrate

exec "$@"
