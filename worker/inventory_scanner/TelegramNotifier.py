import os
import time
import requests
import logging
from typing import Dict, Any, List

# Thiết lập logging
logging.basicConfig(
    filename='runtime.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class TelegramNotifier:
    """Class để gửi tin nhắn và tài liệu đến một chat Telegram cụ thể."""

    def __init__(self, bot_token: str, proxies: Dict[str, str] = None):
        """
        Khởi tạo TelegramNotifier.

        Args:
            bot_token: Token của bot Telegram.
            proxies: Dictionary chứa cấu hình proxy (nếu có).
        """
        if not bot_token:
            raise ValueError("Bot token không được để trống.")
        
        self.bot_token = bot_token
        self.proxies = proxies
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, chat_id: str, message_text: str):
        """
        Gửi một tin nhắn văn bản đến một chat_id cụ thể.

        Args:
            chat_id: ID của cuộc trò chuyện cần gửi tin nhắn đến.
            message_text: Nội dung tin nhắn. Hỗ trợ định dạng HTML.
        """
        if not chat_id:
            logging.warning("chat_id trống, không thể gửi tin nhắn.")
            return

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message_text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            response = requests.post(url, json=payload, proxies=self.proxies, timeout=15)
            
            if response.status_code == 200:
                logging.info(f"Đã gửi tin nhắn thành công đến chat_id {chat_id}.")
            else:
                logging.error(f"Lỗi khi gửi tin nhắn đến {chat_id}: {response.status_code} - {response.text}")
                logging.error(f"Nội dung tin nhắn lỗi: {message_text[:200]}...")

        except requests.exceptions.RequestException as e:
            logging.error(f"Lỗi RequestException khi gửi tin nhắn đến {chat_id}: {e}")
        except Exception as e:
            logging.error(f"Lỗi không xác định khi gửi tin nhắn: {e}")

    def format_message(self, result: Dict[str, Any]) -> str:
        """
        Định dạng một tin nhắn chuẩn từ kết quả so sánh đã được gom nhóm.
        """
        agent_name = result.get('agent_name', 'Không xác định')
        project_name = result.get('project_name', 'Không xác định')
        comparison = result.get('comparison', {})
        
        added = sorted(list(set(comparison.get('added', []))))
        removed = sorted(list(set(comparison.get('removed', []))))
        changed = comparison.get('changed', [])
        
        # Chỉ tạo tin nhắn nếu có ít nhất một thay đổi
        if not added and not removed and not changed:
            return "" 

        message = f"🏢 <b>Đại lý:</b> {agent_name}\n"
        message += f"📋 <b>Dự án:</b> {project_name}\n\n"

        if added:
            added_str = "\n".join([f"<b>{key}</b>" for key in added])
            message += f"➕ <b>Nhập thêm ({len(added)}):</b>\n<blockquote>{added_str}</blockquote>\n\n"
        else:
            message += "➕ <b>Nhập thêm:</b> Không có\n\n"

        if removed:
            removed_str = "\n".join([f"<b>{key}</b>" for key in removed])
            message += f"✅ <b>Đã bán ({len(removed)}):</b>\n<blockquote>{removed_str}</blockquote>\n\n"
        else:
            message += "✅ <b>Đã bán:</b> Không có\n\n"
            
        if changed:
            changed_str = "\n".join([f"<b>{c['key']}</b>: {c['old']} → {c['new']}" for c in changed])
            message += f"✏️ <b>Thay đổi ({len(changed)}):</b>\n<blockquote>{changed_str}</blockquote>"
        else:
            message += "✏️ <b>Thay đổi:</b> Không có"
            
        return message.strip()
