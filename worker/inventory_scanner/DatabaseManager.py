import sqlite3
import logging
import json
import datetime
from datetime import timezone
from typing import List, Optional, Any, Dict

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Quản lý tất cả các tương tác với cơ sở dữ liệu SQLite."""

    def __init__(self, db_file: str = 'app.db'):
        self.db_file = db_file
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Đã kết nối thành công đến database: {self.db_file}")
        except sqlite3.Error as e:
            logger.error(f"Lỗi khi kết nối đến database: {e}")
            raise

    def get_active_configs(self) -> List[sqlite3.Row]:
        """Lấy danh sách tất cả các cấu hình đang hoạt động."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT
                    pc.*,
                    p.name as project_name,
                    p.key_prefixes,
                    p.telegram_chat_id,
                    a.name as agent_name
                FROM
                    management_projectconfig pc
                JOIN
                    management_agent a ON pc.agent_id = a.id
                JOIN
                    management_project p ON pc.project_id = p.id
                WHERE
                    pc.is_active = 1;
            """)
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Lỗi khi lấy danh sách cấu hình: {e}")
            return []

    def get_latest_snapshot(self, project_config_id: int) -> Optional[Dict[str, Any]]:
        """Lấy snapshot gần nhất của một cấu hình dự án."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT data FROM management_snapshot
                WHERE project_data_source_id = ?
                ORDER BY timestamp DESC
                LIMIT 1;
            """, (project_config_id,))
            result = cursor.fetchone()
            return json.loads(result['data']) if result else None
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Lỗi khi lấy snapshot gần nhất cho project_config_id {project_config_id}: {e}")
            return None

    def add_snapshot(self, project_config_id: int, data: Dict[str, Any]):
        """Thêm một snapshot mới cho một cấu hình dự án."""
        try:
            cursor = self.conn.cursor()
            current_timestamp = datetime.datetime.now(timezone.utc)
            cursor.execute("""
                INSERT INTO management_snapshot (timestamp, project_data_source_id, data)
                VALUES (?, ?, ?);
            """, (current_timestamp, project_config_id, json.dumps(data, ensure_ascii=False)))
            self.conn.commit()
            logger.info(f"Đã thêm snapshot mới cho project_config_id {project_config_id}")
        except sqlite3.Error as e:
            logger.error(f"Lỗi khi thêm snapshot: {e}")
            self.conn.rollback()

    def sync_apartment_units(self, project_config_id: int, new_snapshot: Dict[str, Dict[str, Any]]):
        """
        Đồng bộ bảng ApartmentUnit với snapshot mới nhất, bao gồm cả việc cập nhật dữ liệu.
        - Xóa các căn không còn.
        - Thêm các căn mới.
        - Cập nhật các căn đã có nếu thông tin thay đổi (VD: CSBH).
        """
        if not self.conn: return

        try:
            cursor = self.conn.cursor()

            cursor.execute("SELECT unit_code, sales_policy FROM management_apartmentunit WHERE project_config_id = ?", (project_config_id,))
            db_units = {row['unit_code']: dict(row) for row in cursor.fetchall()}
            db_unit_codes = set(db_units.keys())

            snapshot_unit_codes = set(new_snapshot.keys())
            units_to_remove = db_unit_codes - snapshot_unit_codes
            if units_to_remove:
                params_to_delete = [(project_config_id, code) for code in units_to_remove]
                cursor.executemany("DELETE FROM management_apartmentunit WHERE project_config_id = ? AND unit_code = ?", params_to_delete)
                logger.info(f"[{project_config_id}] Đã xóa {len(units_to_remove)} căn khỏi quỹ căn.")

            units_to_add = []
            units_to_update = []
            timestamp = datetime.datetime.now(timezone.utc)

            for unit_code, unit_data in new_snapshot.items():
                new_policy = unit_data.get('sales_policy')

                if unit_code not in db_unit_codes:
                    units_to_add.append((project_config_id, unit_code, new_policy, timestamp, timestamp))
                else:
                    current_policy = db_units[unit_code].get('sales_policy')
                    if current_policy != new_policy:
                        units_to_update.append((new_policy, timestamp, project_config_id, unit_code))

            if units_to_add:
                cursor.executemany(
                    "INSERT INTO management_apartmentunit (project_config_id, unit_code, sales_policy, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    units_to_add
                )
                logger.info(f"[{project_config_id}] Đã thêm {len(units_to_add)} căn mới vào quỹ căn.")

            if units_to_update:
                cursor.executemany(
                    "UPDATE management_apartmentunit SET sales_policy = ?, updated_at = ? WHERE project_config_id = ? AND unit_code = ?",
                    units_to_update
                )
                logger.info(f"[{project_config_id}] Đã cập nhật {len(units_to_update)} căn trong quỹ căn.")

            if units_to_remove or units_to_add or units_to_update:
                self.conn.commit()
            else:
                logger.info(f"[{project_config_id}] Quỹ căn không có thay đổi.")

        except sqlite3.Error as e:
            logger.error(f"Lỗi khi đồng bộ quỹ căn cho project_config_id {project_config_id}: {e}")
            self.conn.rollback()

    def add_inventory_change(self, project_config_id: int, change_type: str, apartment_key: str, details: Dict[str, Any]):
        """Thêm một bản ghi thay đổi vào bảng InventoryChange."""
        if not self.conn:
            return
        try:
            cursor = self.conn.cursor()
            current_timestamp = datetime.datetime.now(timezone.utc)
            cursor.execute("""
                INSERT INTO management_inventorychange (project_config_id, timestamp, change_type, apartment_key, details)
                VALUES (?, ?, ?, ?, ?);
            """, (project_config_id, current_timestamp, change_type, apartment_key, json.dumps(details, ensure_ascii=False)))
            self.conn.commit()
            logger.info(f"Đã ghi nhận thay đổi '{change_type}' cho căn hộ '{apartment_key}' của dự án {project_config_id}")
        except sqlite3.Error as e:
            logger.error(f"Lỗi khi thêm bản ghi InventoryChange: {e}")
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
            return [dict(mapping) for mapping in mappings]
        except sqlite3.Error as e:
            logger.error(f"Không thể lấy column mappings cho project {project_config_id}: {e}")
            return []

    def close(self):
        """Đóng kết nối database."""
        if self.conn:
            self.conn.close()
