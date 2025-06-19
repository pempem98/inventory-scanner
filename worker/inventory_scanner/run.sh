#!/bin/bash

# --- Cấu hình ---
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
echo "The script's absolute directory is: $SCRIPT_DIR"

# --- Bắt đầu Script ---
echo "-------------------------------------------"
echo "Bắt đầu thực thi tác vụ..."
echo "Thư mục làm việc: $SCRIPT_DIR"
echo "-------------------------------------------"

# Kiểm tra và chuyển đến thư mục làm việc
if [ ! -d "$SCRIPT_DIR" ]; then
  echo "Lỗi: Thư mục làm việc '$SCRIPT_DIR' không tồn tại."
  exit 1
fi
cd "$SCRIPT_DIR" || exit 1

# Ngăn Python tạo __pycache__
export PYTHONDONTWRITEBYTECODE=1

# Cài lại thư viện nếu cần thiết
# pip install -r requirements.txt --no-cache-dir

# Tác vụ 1: Cập nhật Sale Admin Inventory với cơ chế ghi log mới
echo "Đang chạy Sale Admin Inventory Scanner (SAIS)..."

DATETIME=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="logs/$DATETIME"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/stdout.log"

echo "File log sẽ được lưu tại: $LOG_FILE"

# Tác vụ 2: Chạy Sale Admin Inventory Scanner
python3 main.py >> "$LOG_FILE" 2>&1
[ ! -f *.log ] || mv *.log "$LOG_DIR"

if [ $? -eq 0 ]; then
  echo "SAIS đã hoàn thành thành công."
else
  echo "Lỗi: SAIS đã thất bại. Vui lòng kiểm tra file log để biết chi tiết:"
  echo "$LOG_FILE"
  exit 1
fi

echo "-------------------------------------------"
echo "Tất cả các tác vụ đã hoàn tất."
echo "-------------------------------------------"