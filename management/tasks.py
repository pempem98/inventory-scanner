# management/tasks.py

import os
import logging
import shutil
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.conf import settings
from worker.inventory_scanner.InventoryScanner import InventoryScanner

# Lấy ra logger đã được cấu hình sẵn bởi Django/Celery
logger = logging.getLogger(__name__)


@shared_task(name="tasks.scan_all_inventories")
def scan_all_inventories_task():
    """
    Tác vụ Celery cụ thể để quét tất cả các kho hàng (inventories).
    Đây là tác vụ mà chúng ta sẽ lập lịch trong Django Admin.
    """
    logger.info("Bắt đầu tác vụ quét kho hàng...")
    try:
        # Khởi tạo và chạy scanner
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise RuntimeError("Lỗi: Vui lòng thiết lập biến môi trường TELEGRAM_BOT_TOKEN.")

        # Khởi tạo scanner với token, không dùng proxy
        proxies = {
            'http': 'http://rb-proxy-apac.bosch.com:8080',
            'https': 'http://rb-proxy-apac.bosch.com:8080'
        }
        scanner = InventoryScanner(bot_token=bot_token, proxies=proxies)
        scanner.run()

        logger.info("Hoàn thành tác vụ quét kho hàng thành công.")
        return "Scan completed successfully."
    except Exception as e:
        logger.error(f"Đã xảy ra lỗi trong quá trình quét kho hàng: {e}", exc_info=True)
        return f"Scan failed with error: {e}"


@shared_task(name="tasks.backup_database")
def backup_database_task():
    """
    Sao chép file database SQLite ra một thư mục backup.
    Tên file backup sẽ có dạng: app_backup_YYYYMMDD_HHMMSS.db
    """
    # Lấy đường dẫn database từ settings
    db_source_path = Path(settings.DATABASES['default']['NAME'])
    
    # Định nghĩa thư mục chứa các bản backup (đường dẫn bên trong container)
    backup_dir = Path("/app/backups")
    
    logger.info(f"Bắt đầu tác vụ sao lưu database từ: {db_source_path}")
    
    # Đảm bảo thư mục backup tồn tại
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Tạo tên file backup với timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"app_backup_{timestamp}.db"
    db_backup_path = backup_dir / backup_file_name
    
    if not db_source_path.exists():
        logger.error(f"Không tìm thấy file database nguồn tại: {db_source_path}")
        return "Source database not found."
        
    try:
        # Thực hiện sao chép file
        shutil.copyfile(db_source_path, db_backup_path)
        logger.info(f"Đã tạo backup database thành công tại: {db_backup_path}")
        return f"Backup successful: {db_backup_path}"
    except Exception as e:
        logger.error(f"Tạo backup database thất bại: {e}", exc_info=True)
        return f"Backup failed: {e}"
