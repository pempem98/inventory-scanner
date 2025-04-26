import os
import logging
import requests
from typing import List, Dict, Any

# Thiết lập logging
logging.basicConfig(
    filename='runtime.log',
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
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_document(self, file_path: str) -> None:
        """Gửi file báo cáo qua Telegram dưới dạng tài liệu.

        Args:
            file_path: Đường dẫn đến file cần gửi (e.g., Excel report).
        """
        if not self.bot_token or not self.chat_id:
            logging.warning("Thiếu bot_token hoặc chat_id, không gửi file.")
            return

        if not os.path.exists(file_path):
            logging.error(f"File {file_path} không tồn tại, không gửi.")
            return

        try:
            url = f"{self.base_url}/sendDocument"
            with open(file_path, 'rb') as file:
                files = {'document': (os.path.basename(file_path), file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
                data = {'chat_id': self.chat_id}
                response = requests.post(url, data=data, files=files, timeout=30)
                if response.status_code != 200:
                    logging.error(f"Gửi file thất bại: {response.text}")
                else:
                    logging.info(f"Đã gửi file: {file_path}")
        except Exception as e:
            logging.error(f"Lỗi khi gửi file {file_path}: {e}")

    def send_message(self, results: List[Dict[str, Any]]=[], messages: List[str]=[]) -> None:
        """Gửi tin nhắn Telegram với thông tin căn thêm mới, đã bán và lỗi."""
        if not self.bot_token or not self.chat_id:
            logging.warning("Thiếu cấu hình Telegram (bot_token hoặc chat_id) trong workflow_config.json.")
            return

        # Tạo nội dung tin nhắn
        if not messages:
            for result in results:
                agent_name = str(result['agent_name'])
                project_name = str(result['project_name'])
                message = result.get('message', '')
                if message:
                    url = result.get('url', None)
                    message += f'\n<b>Link:</b> <a href="{url}" target="_blank">{agent_name}_{project_name}</a>'
                else:
                    # Ánh xạ project_name thành tên dự án ngắn (như LSB)
                    project_prefix = self.workflow_config.get('project_prefix', {})
                    short_project_name = project_name
                    for prefix, name in project_prefix.items():
                        if project_name.startswith(prefix):
                            short_project_name = name
                            break

                    # Lấy thông tin so sánh
                    comparison = result.get('comparison', {})
                    added = comparison.get('added', [])
                    removed = comparison.get('removed', [])
                    remaining = comparison.get('remaining', [])

                    if not added and not removed:
                        continue

                    message = f"🏢 <b>Đại lý</b>: {agent_name}\n"
                    message += f"📋 <b>Dự án</b>: {short_project_name}\n\n"
                    if added:
                        message += "➕ <b>Nhập thêm</b>:\n<blockquote expandable>" + "\n".join([f"<b>{key}</b>" for key in added]) + "</blockquote>\n\n"
                    else:
                        message += "➕ <b>Nhập thêm</b>: Không có\n\n"
                    if removed:
                        message += "✅ <b>Đã bán</b>:\n<blockquote expandable>" + "\n".join([f"<b>{key}</b>" for key in removed]) + "</blockquote>"
                        if remaining:
                            message += "\n\n📊 <b>Quỹ căn hiện tại</b>:\n<blockquote expandable>" + "\n".join([f"<b>{key}</b>" for key in remaining]) + "</blockquote>"
                        else:
                            message += "\n\n📊 <b>Quỹ căn hiện tại</b>: Không có"
                    else:
                        message += "✅ <b>Đã bán</b>: Không có"

                messages.append(message)

        # Gửi từng tin nhắn
        for message in messages:
            try:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                }
                response = requests.post(url, json=payload, proxies=self.proxies)
                if response.status_code == 200:
                    logging.info(f"Đã gửi tin nhắn Telegram: {message[:100]}...")
                else:
                    logging.error(f"Lỗi khi gửi tin nhắn Telegram: {response.text}")
            except Exception as e:
                logging.error(f"Lỗi khi gửi tin nhắn Telegram: {e}")

    def notify(self, results: Dict[str, Dict[str, Dict[str, List]]], report_file: str) -> None:
        """Gửi thông báo Telegram với kết quả so sánh và đường dẫn file báo cáo."""
        if not self.bot_token or not self.chat_id:
            logging.warning("Thiếu cấu hình Telegram (bot_token hoặc chat_id) trong workflow_config.json.")
            return

        # Chuyển đổi results sang định dạng danh sách
        converted_results = []
        for result in results:
            agent_name = result.get('agent_name', None)
            project_name = result.get('project_name', None)
            comparison = result.get('comparison', {})
            converted_results.append({
                'agent_name': agent_name,
                'project_name': project_name,
                'comparison': {
                    'added': [item for item in comparison.get('added', []) if item and len(item) > 0],
                    'removed': [item for item in comparison.get('removed', []) if item and len(item) > 0],
                    'changed': comparison.get('changed', []),
                    'remaining': [item for item in comparison.get('remaining', []) if item and len(item) > 0]
                },
                'message': result.get('message', None),
                'url': result.get('url', None),
            })

        # Gửi thông báo chính
        self.send_message(converted_results)

        # Gửi đường dẫn file báo cáo
        if report_file:
            self.send_document(file_path=report_file)
