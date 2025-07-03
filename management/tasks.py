import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from worker.inventory_scanner.InventoryScanner import InventoryScanner
from .models import SystemConfig, WorkerLog, InventoryChange, Snapshot

# Lấy ra logger đã được cấu hình sẵn bởi Django/Celery
logger = logging.getLogger(__name__)


@shared_task(name="tasks.scan_all_inventories")
def scan_all_inventories_task():
    """
    Tác vụ Celery để quét tất cả kho hàng.
    Lấy cấu hình (bot token, proxy) từ model SystemConfig.
    """
    logger.info("Bắt đầu tác vụ quét kho hàng...")
    try:
        # Tải cấu hình từ database
        config = SystemConfig.load()
        bot_token = config.telegram_bot_token
        proxy_url = config.proxy_url

        if not bot_token:
            raise RuntimeError("Lỗi: Telegram Bot Token chưa được thiết lập trong Cấu hình hệ thống.")

        proxies = None
        if proxy_url:
            proxies = {'http': proxy_url, 'https': proxy_url}
            logger.info(f"Sử dụng proxy: {proxy_url}")

        # Khởi tạo scanner với token và proxy
        scanner = InventoryScanner(bot_token=bot_token, proxies=proxies)
        scanner.run()

        logger.info("Hoàn thành tác vụ quét kho hàng thành công.")
        return "Scan completed successfully."
    except Exception as e:
        logger.error(f"Đã xảy ra lỗi trong quá trình quét kho hàng: {e}", exc_info=True)
        return f"Scan failed with error: {e}"


@shared_task(name="tasks.cleanup_old_records")
def cleanup_old_records_task():
    """
    Tác vụ Celery để dọn dẹp các bản ghi và log cũ hơn 30 ngày.
    """
    days_to_keep = 30
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    logger.info(f"Bắt đầu tác vụ dọn dẹp. Xóa các bản ghi cũ hơn ngày: {cutoff_date.strftime('%Y-%m-%d')}")

    try:
        # Xóa WorkerLog cũ
        logs_deleted, _ = WorkerLog.objects.filter(timestamp__lt=cutoff_date).delete()
        logger.info(f"Đã xóa {logs_deleted} bản ghi WorkerLog cũ.")

        # Xóa InventoryChange cũ
        changes_deleted, _ = InventoryChange.objects.filter(timestamp__lt=cutoff_date).delete()
        logger.info(f"Đã xóa {changes_deleted} bản ghi InventoryChange cũ.")

        # Xóa Snapshot cũ
        snapshots_deleted, _ = Snapshot.objects.filter(timestamp__lt=cutoff_date).delete()
        logger.info(f"Đã xóa {snapshots_deleted} bản ghi Snapshot cũ.")

        logger.info("Hoàn thành tác vụ dọn dẹp thành công.")
        return f"Cleanup successful. Deleted: {logs_deleted} logs, {changes_deleted} changes, {snapshots_deleted} snapshots."
    except Exception as e:
        logger.error(f"Tác vụ dọn dẹp thất bại: {e}", exc_info=True)
        return f"Cleanup failed: {e}"


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