#!/bin/sh

echo "==== Starting Celery Services in Background ===="
# Đảm bảo script run_celery.sh có quyền thực thi
chmod +x ./run_celery.sh
# Khởi động Celery worker và beat ở chế độ nền
./run_celery.sh restart
echo "Celery services started."
echo "==============================================="
echo ""
echo "==== Starting Django Application in Foreground ===="
echo "Current working directory: $(pwd)"
# Dòng này không bắt buộc, nhưng hữu ích để debug
# echo "Environment variables:"
# printenv

# Chạy Django server. Đây sẽ là tiến trình chính giữ cho container hoạt động.
python manage.py runserver 0.0.0.0:8000