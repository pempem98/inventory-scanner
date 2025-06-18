#!/bin/bash

# --- Cấu hình ---
WORKSPACE="/Users/lth_dq_lu/Desktop/workspace/sale-admin-toolkit/worker"

# --- Bắt đầu Script ---
echo "-------------------------------------------"
echo "Bắt đầu thực thi tác vụ..."
echo "Thư mục làm việc: $WORKSPACE"
echo "-------------------------------------------"


# Kiểm tra và chuyển đến thư mục làm việc
if [ ! -d "$WORKSPACE" ]; then
  echo "Lỗi: Thư mục làm việc '$WORKSPACE' không tồn tại."
  exit 1
fi
cd "$WORKSPACE" || exit 1


# Ngăn Python tạo __pycache__
export PYTHONDONTWRITEBYTECODE=1


# Tác vụ 1: Cập nhật Sale Admin Inventory với cơ chế ghi log mới
echo "Đang chạy Sale Admin Inventory Scanner (SAIS)..."

# Tạo thư mục log theo ngày giờ
DATETIME=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="logs/$DATETIME"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/stdout.log"

echo "File log sẽ được lưu tại: $LOG_FILE"

python3 main.py >> "$LOG_FILE" 2>&1
mv runtime.log "$LOG_DIR"

# Kiểm tra mã thoát của lệnh vừa rồi
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