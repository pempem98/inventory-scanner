import sqlite3
import logging
import json
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

    def create_tables(self):
        """Tạo các bảng cần thiết nếu chúng chưa tồn tại."""
        try:
            cursor = self.conn.cursor()
            # Bảng Đại lý
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            """)

            # Bảng Cấu hình Dự án
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER,
                project_name TEXT NOT NULL,
                spreadsheet_id TEXT,
                gid TEXT NOT NULL,
                html_url TEXT,
                telegram_chat_id TEXT,
                is_active INTEGER DEFAULT 1,
                header_row_index INTEGER,
                key_column_aliases TEXT,
                check_columns_aliases TEXT,
                key_prefixes TEXT,
                invalid_colors TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents (id)
            );
            """)

            # Bảng Snapshots
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_config_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                data TEXT NOT NULL,
                FOREIGN KEY (project_config_id) REFERENCES project_configs (id)
            );
            """)
            self.conn.commit()
            logging.info("Đã tạo các bảng (nếu chưa tồn tại) thành công.")
        except sqlite3.Error as e:
            logging.error(f"Lỗi khi tạo bảng: {e}")
            self.conn.rollback()
            raise

    def get_active_configs(self) -> List[sqlite3.Row]:
        """Lấy danh sách tất cả các cấu hình đang hoạt động."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT pc.*, a.name as agent_name
                FROM project_configs pc
                JOIN agents a ON pc.agent_id = a.id
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
                SELECT data FROM snapshots
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
            cursor.execute("""
                INSERT INTO snapshots (project_config_id, data)
                VALUES (?, ?);
            """, (project_config_id, json.dumps(data, ensure_ascii=False)))
            self.conn.commit()
            logging.info(f"Đã thêm snapshot mới cho project_config_id {project_config_id}")
        except sqlite3.Error as e:
            logging.error(f"Lỗi khi thêm snapshot: {e}")
            self.conn.rollback()

    def close(self):
        """Đóng kết nối database."""
        if self.conn:
            self.conn.close()
