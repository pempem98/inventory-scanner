import os
from InventoryScanner import InventoryScanner

if __name__ == "__main__":
    # Lấy BOT_TOKEN từ biến môi trường để bảo mật
    # Ví dụ: export TELEGRAM_BOT_TOKEN="your_token_here"
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    proxies = {
        'http': 'http://rb-proxy-apac.bosch.com:8080',
        'https': 'http://rb-proxy-apac.bosch.com:8080'
    }
    if not bot_token:
        print("Lỗi: Vui lòng thiết lập biến môi trường TELEGRAM_BOT_TOKEN.")
    else:
        # Khởi tạo và chạy workflow
        manager = InventoryScanner(bot_token=bot_token, proxies=None)
        manager.run()