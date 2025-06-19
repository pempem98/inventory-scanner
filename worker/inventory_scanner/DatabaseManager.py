import sqlite3
import logging
import json
import datetime
from typing import List, Optional, Any, Dict

# Thiết lập logging
logging.basicConfig(
    filename='runtime.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class DatabaseManager:
    """Quản lý tất cả các tương tác với cơ sở dữ liệu SQLite."""

    def __init__(self, db_file: str = 'app.db'):
        self.db_file = db_file
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
            logging.info(f"Đã kết nối thành công đến database: {self.db_file}")
        except sqlite3.Error as e:
            logging.error(f"Lỗi khi kết nối đến database: {e}")
            raise

    def get_active_configs(self) -> List[sqlite3.Row]:
        """Lấy danh sách tất cả các cấu hình đang hoạt động."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT pc.*, a.name as agent_name
                FROM management_projectconfig pc
                JOIN management_agent a ON pc.agent_id = a.id
                WHERE pc.is_active = 1;
            """)
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Lỗi khi lấy danh sách cấu hình: {e}")
            return []

    def get_latest_snapshot(self, project_config_id: int) -> Optional[Dict[str, Any]]:
        """Lấy snapshot gần nhất của một cấu hình dự án."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT data FROM management_snapshot
                WHERE project_config_id = ?
                ORDER BY timestamp DESC
                LIMIT 1;
            """, (project_config_id,))
            result = cursor.fetchone()
            return json.loads(result['data']) if result else None
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logging.error(f"Lỗi khi lấy snapshot gần nhất cho project_config_id {project_config_id}: {e}")
            return None

    def add_snapshot(self, project_config_id: int, data: Dict[str, Any]):
        """Thêm một snapshot mới cho một cấu hình dự án."""
        try:
            cursor = self.conn.cursor()
            current_timestamp = datetime.datetime.now()
            cursor.execute("""
                INSERT INTO management_snapshot (timestamp, project_config_id, data)
                VALUES (?, ?, ?);
            """, (current_timestamp, project_config_id, json.dumps(data, ensure_ascii=False)))
            self.conn.commit()
            logging.info(f"Đã thêm snapshot mới cho project_config_id {project_config_id}")
        except sqlite3.Error as e:
            logging.error(f"Lỗi khi thêm snapshot: {e}")
            self.conn.rollback()

    def get_column_mappings(self, project_config_id):
        """Lấy tất cả các column mappings cho một project config ID."""
        if not self.conn: return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT internal_name, display_name, aliases, is_identifier
                FROM management_columnmapping
                WHERE project_config_id = ?
            """, (project_config_id,))
            mappings = cursor.fetchall()
            # Chuyển đổi từ tuple sang dict để dễ sử dụng
            return [dict(mapping) for mapping in mappings]
        except sqlite3.Error as e:
            logging.error(f"Không thể lấy column mappings cho project {project_config_id}: {e}")
            return []

    def close(self):
        """Đóng kết nối database."""
        if self.conn:
            self.conn.close()
