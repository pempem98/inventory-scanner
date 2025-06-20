#!/bin/bash

# Tên project của bạn (thư mục chứa settings.py)
PROJECT_NAME="configuration"

# Thư mục để lưu file PID (Process ID)
PID_DIR="logs/pids"
mkdir -p $PID_DIR

# Đường dẫn file PID
WORKER_PID_FILE="$PID_DIR/worker.pid"
BEAT_PID_FILE="$PID_DIR/beat.pid"

# Hàm để bắt đầu các tiến trình
start() {
    echo "Starting Celery services..."
    echo "Logs will be handled by Django's LOGGING setting (e.g., to logs/runtime.log)."

    # Kiểm tra xem Worker đã chạy chưa
    if [ -f $WORKER_PID_FILE ]; then
        echo "Celery Worker is already running (PID file exists)."
    else
        echo "Starting Celery Worker with gevent pool..."
        celery -A $PROJECT_NAME.celery worker -P gevent --detach --pidfile=$WORKER_PID_FILE
        echo "Celery Worker started."
    fi

    # Kiểm tra xem Beat đã chạy chưa
    if [ -f $BEAT_PID_FILE ]; then
        echo "Celery Beat is already running (PID file exists)."
    else
        echo "Starting Celery Beat..."
        celery -A $PROJECT_NAME.celery beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --detach --pidfile=$BEAT_PID_FILE
        echo "Celery Beat started."
    fi
}

# Hàm để dừng các tiến trình
stop() {
    echo "Stopping Celery services..."

    # Dừng Worker
    if [ -f $WORKER_PID_FILE ]; then
        echo "Stopping Celery Worker..."
        kill $(cat $WORKER_PID_FILE)
        rm $WORKER_PID_FILE
        echo "Celery Worker stopped."
    else
        echo "Celery Worker is not running (PID file not found)."
    fi

    # Dừng Beat
    if [ -f $BEAT_PID_FILE ]; then
        echo "Stopping Celery Beat..."
        kill $(cat $BEAT_PID_FILE)
        rm $BEAT_PID_FILE
        echo "Celery Beat stopped."
    else
        echo "Celery Beat is not running (PID file not found)."
    fi
}

# Xử lý các tham số dòng lệnh (start, stop, restart)
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2 # Đợi 2 giây để đảm bảo các tiến trình đã dừng hẳn
        start
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
esac

exit 0
