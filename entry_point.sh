#! /bin/sh

echo "Starting the application..."
echo "Current working directory: $(pwd)"
echo "Environment variables:"
printenv
# Execute the main application
python manage.py runserver 0.0.0.0:8000
