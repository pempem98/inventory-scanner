import os
import logging
from celery import shared_task
from worker.inventory_scanner.InventoryScanner import InventoryScanner

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
        proxies = {
            'http': 'http://rb-proxy-apac.bosch.com:8080',
            'https': 'http://rb-proxy-apac.bosch.com:8080'
        }
        if not bot_token:
            raise RuntimeError("Lỗi: Vui lòng thiết lập biến môi trường TELEGRAM_BOT_TOKEN.")
        else:
            scanner = InventoryScanner(bot_token=bot_token, proxies=None)
            scanner.run()
            logger.info("Hoàn thành tác vụ quét kho hàng thành công.")
            return "Scan completed successfully."
    except Exception as e:
        logger.error(f"Đã xảy ra lỗi trong quá trình quét kho hàng: {e}", exc_info=True)
        return f"Scan failed with error: {e}"
