#!/bin/bash

# Định nghĩa thư mục làm việc
WORKSPACE="/home/ubuntu/workspace/sale-admin-toolkit"

# Kiểm tra thư mục tồn tại
if [ ! -d "$WORKSPACE" ]; then
  echo "Error: Directory $WORKSPACE does not exist"
  exit 1
fi

# Chuyển đến thư mục làm việc
cd "$WORKSPACE" || exit 1

# Kích hoạt môi trường ảo
source .venv/bin/activate

# Ngăn Python tạo __pycache__
export PYTHONDONTWRITEBYTECODE=1

# Tác vụ 1: Cập nhật Sale Admin Inventory
echo "Running WorkflowManager.py..."
python3 WorkflowManager.py
if [ $? -eq 0 ]; then
  mv runtime.log "./reports/runtime_$(date +%Y%m%d_%H%M).log"
  echo "WorkflowManager.py completed, log moved"
else
  echo "Error: WorkflowManager.py failed"
  exit 1
fi

# Tác vụ 2: Lấy cell key log
echo "Running ExcelBackupExtractor.py..."
mkdir -p ./extracted_data
python3 utils/ExcelBackupExtractor.py
if [ $? -eq 0 ]; then
  mv stdout.log "./extracted_data/stdout_$(date +%Y%m%d_%H%M).log"
  echo "ExcelBackupExtractor.py completed, log moved"
else
  echo "Error: ExcelBackupExtractor.py failed"
  exit 1
fi

# Tác vụ 3: Xóa log và file backup cũ hơn 30 ngày
echo "Removing logs and backup files older than 30 days..."
find ./reports -name "runtime_*.log" -mtime +30 -delete && \
find ./extracted_data -name "stdout_*.log" -mtime +30 -delete && \
find ./backup -type f -path "./backup/backup_*/*" -mtime +30 -delete
if [ $? -eq 0 ]; then
  echo "Old logs and backup files removed successfully"
else
  echo "Error: Failed to remove old logs or backup files"
  exit 1
fi

# Thoát môi trường ảo
deactivate

echo "All tasks completed"