import logging
import requests
from typing import List, Dict, Any

# Thiết lập logging
logging.basicConfig(
    filename='telegram_notifier.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class TelegramNotifier:
    """Class để gửi tin nhắn Telegram về các căn thêm mới, đã bán và lỗi."""

    def __init__(self, workflow_config: Dict[str, Any], proxies: Dict[str, str] = None):
        """
        Khởi tạo TelegramNotifier.

        Args:
            workflow_config: Config từ workflow_config.json chứa telegram settings.
            proxies: Dictionary chứa cấu hình proxy (nếu có).
        """
        self.workflow_config = workflow_config
        self.proxies = proxies
        self.telegram_config = workflow_config.get('telegram', {})
        self.bot_token = self.telegram_config.get('bot_token')
        self.chat_id = self.telegram_config.get('chat_id')

    def send_message(self, results: List[Dict[str, Any]]=[], messages: List[str]=[]) -> None:
        """Gửi tin nhắn Telegram với thông tin căn thêm mới, đã bán và lỗi."""
        if not self.bot_token or not self.chat_id:
            logging.warning("Thiếu cấu hình Telegram (bot_token hoặc chat_id) trong workflow_config.json.")
            return

        # Tạo nội dung tin nhắn
        if not messages:
            for result in results:
                agent_name = result['agent_name']
                project_name = result['project_name']
                # Ánh xạ project_name thành tên dự án ngắn (như LSB)
                project_prefix = self.workflow_config.get('project_prefix', {})
                short_project_name = project_name
                for prefix, name in project_prefix.items():
                    if project_name.startswith(prefix):
                        short_project_name = name
                        break

                # Trường hợp lỗi (status = 'Failed')
                if result['status'] == 'Failed':
                    message = f"[Lỗi] Đại lý {agent_name} - Dự án {short_project_name}"
                    messages.append(message)
                    continue

                # Trường hợp thành công (status = 'Success')
                if result['status'] != 'Success':
                    continue

                added = result['comparison'].get('added', [])
                removed = result['comparison'].get('removed', [])
                remaining = result['comparison'].get('remaining', [])

                if not added and not removed:
                    continue

                message = f"Đại lý {agent_name}\nDự án {short_project_name}\n\n"
                if added:
                    message += "Nhập thêm:\n" + "\n".join([f"<b>{key}</b>" for key in remaining]) + "\n\n"
                else:
                    message += "Nhập thêm: Không có\n\n"
                if removed:
                    message += "Đã bán:\nĐã bán " + "\nĐã bán ".join([f"<b>{key}</b>" for key in removed])
                    message += "\n\nQuỹ căn hiện tại:\n<blockquote>" + "\n".join([f"<b>{key}</b>" for key in removed]) + "</blockquote>"
                else:
                    message += "Đã bán: Không có"

                messages.append(message)

        # Gửi từng tin nhắn
        for message in messages:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, json=payload, proxies=self.proxies)
                if response.status_code == 200:
                    logging.info(f"Đã gửi tin nhắn Telegram: {message[:100]}...")
                else:
                    logging.error(f"Lỗi khi gửi tin nhắn Telegram: {response.text}")
            except Exception as e:
                logging.error(f"Lỗi khi gửi tin nhắn Telegram: {e}")

if __name__ == "__main__":
    # Ví dụ sử dụng TelegramNotifier
    sample_workflow_config = {
        "project_prefix": {
            "C3": "LSB",
            "C4": "MGA"
        },
        "telegram": {
            "bot_token": "8067863112:AAGgxTH48MEXmtK8IMvOIKWtiFa5yGcf4C0",  # Thay bằng bot token thực
            "chat_id": "-4646944138"       # Thay bằng chat ID thực
        }
    }

    sample_results = [
        {
            "agent_name": "ATD",
            "project_name": "C3_LSB",
            "status": "Success",
            "comparison": {
                "added": ["C3_Product_001", "C3_Product_002"],
                "removed": ["C3_Product_003"],
                "changed": []
            }
        },
        {
            "agent_name": "XYZ",
            "project_name": "C4_MGA",
            "status": "Failed",
            "comparison": {
                "added": [],
                "removed": [],
                "changed": []
            }
        },
        {
            "agent_name": "HOMEPLUS",
            "project_name": "C5_MLS",
            "status": "Failed",
            "comparison": {
                "added": [],
                "removed": [],
                "changed": []
            }
        }
    ]

    sample_proxies = {
        'http': 'http://rb-proxy-apac.bosch.com:8080',
        'https': 'http://rb-proxy-apac.bosch.com:8080'
    }

    # Khởi tạo và gửi tin nhắn thử
    notifier = TelegramNotifier(sample_workflow_config)
    notifier.send_message(sample_results)