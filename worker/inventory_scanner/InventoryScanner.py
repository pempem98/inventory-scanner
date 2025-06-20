import os
import json
import time
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Import các module đã được tùy chỉnh
from .DatabaseManager import DatabaseManager
from .GoogleSheetDownloader import GoogleSheetDownloader
from .TelegramNotifier import TelegramNotifier

logger = logging.getLogger(__name__)

class InventoryScanner:
    """
    Quản lý luồng công việc chính: tải, so sánh, và thông báo dữ liệu
    dựa trên cấu hình từ cơ sở dữ liệu SQLite.
    """

    def __init__(self, bot_token: str, proxies: Optional[Dict[str, str]] = None):
        """
        Khởi tạo InventoryScanner.
        """
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app.db")
        self.db_manager = DatabaseManager(db_file=db_path)
        self.proxies = proxies
        if bot_token:
            self.notifier = TelegramNotifier(bot_token=bot_token, proxies=self.proxies)
        else:
            self.notifier = None
            logger.warning("Không có BOT_TOKEN, sẽ không có thông báo nào được gửi.")

    def _find_header_and_columns(self, df: pd.DataFrame, config: dict, mappings: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Tự động tìm hàng header và vị trí của tất cả các cột được định nghĩa trong danh sách `mappings`.

        Args:
            df: DataFrame chứa dữ liệu từ file nguồn.
            config: Dictionary chứa thông tin cấu hình của dự án.
            mappings: Danh sách các dictionary, mỗi cái chứa thông tin của một ColumnMapping.

        Returns:
            Một dictionary chứa thông tin về header và vị trí các cột, hoặc None nếu thất bại.
        """
        if not mappings:
            logger.error(f"Dự án {config['project_name']} không có cấu hình cột (column mappings) nào.")
            return None

        identifier_map = next((m for m in mappings if m.get('is_identifier')), None)
        if not identifier_map:
            logger.error(f"Dự án {config['project_name']} không có cột nào được đánh dấu là 'is_identifier: true'.")
            return None

        header_row_idx = -1
        config_header_idx = config.get('header_row_index')
        if config_header_idx and 0 < int(config_header_idx) <= len(df):
            header_row_idx = int(config_header_idx) - 1
        else:
            try:
                identifier_aliases = {str(alias).lower() for alias in json.loads(identifier_map.get('aliases', '[]'))}
                if not identifier_aliases:
                    logger.error(f"Cột định danh '{identifier_map['internal_name']}' không có 'aliases' nào được cấu hình.")
                    return None

                for i, row in df.head(10).iterrows():
                    row_values = {str(val).strip().lower() for val in row.dropna().values}
                    if not identifier_aliases.isdisjoint(row_values):
                        header_row_idx = i
                        break
            except json.JSONDecodeError:
                logger.error(f"Lỗi JSON trong 'aliases' của cột định danh cho dự án {config['project_name']}.")
                return None

        if header_row_idx == -1:
            logger.error(f"Không thể tự động tìm thấy hàng header cho dự án {config['project_name']}.")
            return None

        def normalize_column_name(name: str):
            normalized_name = str(name).strip().lower() \
                .replace(' ', '').replace('\n', '').replace(')', '').replace('(', '') \
                .replace('&', '+').replace('và', '+').replace(',', '+')
            return normalized_name

        header_content = [normalize_column_name(h) for h in df.iloc[header_row_idx].tolist()]

        column_indices = {}
        for mapping in mappings:
            internal_key = mapping['internal_name']
            col_idx = None
            try:
                aliases = [normalize_column_name(alias) for alias in json.loads(mapping.get('aliases', '[]'))]
                for alias in aliases:
                    try:
                        col_idx = header_content.index(alias)
                        break
                    except ValueError:
                        continue
                column_indices[internal_key] = col_idx
            except json.JSONDecodeError:
                logger.error(f"Lỗi JSON trong 'aliases' của cột '{internal_key}' cho dự án {config['project_name']}.")
                column_indices[internal_key] = None

        identifier_key_name = identifier_map['internal_name']
        if column_indices.get(identifier_key_name) is None:
            logger.error(f"Không tìm thấy cột định danh '{identifier_key_name}' trong header của dự án {config['project_name']}.")
            return None

        logger.info(f"Đã xác định header ở dòng {header_row_idx + 1}. Các chỉ số cột: {column_indices}")

        return {
            "header_row_idx": header_row_idx,
            "identifier_key": identifier_key_name,
            "column_indices": column_indices,
            "header": header_content
        }

    def _normalize_and_validate_key(self, key: Any, prefixes: Optional[List[str]]) -> Optional[str]:
        if not isinstance(key, (str, int, float)): return None
        clean_key = str(key).strip().upper()
        if not clean_key: return None
        if not prefixes: return clean_key
        for prefix in prefixes:
            if clean_key.startswith(prefix.upper()):
                return clean_key
        return None

    def _extract_snapshot_data(self, data_df: pd.DataFrame, color_df: pd.DataFrame, header_info: dict, config: dict) -> Dict[str, Any]:
        """
        Trích xuất dữ liệu snapshot dựa trên cấu trúc header_info linh hoạt.
        """
        snapshot_data = {}
        identifier_key = header_info['identifier_key']
        column_indices = header_info['column_indices']
        identifier_col_idx = column_indices[identifier_key]

        invalid_colors_json = config.get('invalid_colors', '[]')
        invalid_colors = {c.lower() for c in json.loads(invalid_colors_json)}

        data_rows_df = data_df.iloc[header_info['header_row_idx'] + 1:]
        color_rows_df = color_df.iloc[header_info['header_row_idx'] + 1:]

        prefixes_json = config.get('key_prefixes')
        valid_prefixes = json.loads(prefixes_json) if prefixes_json else None

        for index, row in data_rows_df.iterrows():
            raw_key = row.iloc[identifier_col_idx]
            valid_key = self._normalize_and_validate_key(raw_key, valid_prefixes)

            if valid_key:
                try:
                    cell_color = color_rows_df.loc[index].iloc[identifier_col_idx]
                    if cell_color and cell_color.lower() in invalid_colors:
                        logger.info(f"Bỏ qua key '{valid_key}' do có màu không hợp lệ: {cell_color}")
                        continue
                except (KeyError, IndexError):
                    pass

                row_data = {}
                for key, col_idx in column_indices.items():
                    if key == identifier_key or col_idx is None:
                        continue

                    value = row.iloc[col_idx]
                    row_data[key] = str(value) if pd.notna(value) else None

                snapshot_data[valid_key] = row_data

        return snapshot_data

    def _compare_snapshots(self, new_snapshot: Dict, old_snapshot: Dict) -> Dict[str, List]:
        """
        So sánh hai snapshot, bao gồm tất cả các trường dữ liệu (price, policy, v.v.).
        """
        new_keys = set(new_snapshot.keys())
        old_keys = set(old_snapshot.keys())

        added = sorted(list(new_keys - old_keys))
        removed = sorted(list(old_keys - new_keys))

        changed = []
        common_keys = new_keys.intersection(old_keys)
        for key in common_keys:
            old_data = old_snapshot.get(key, {})
            new_data = new_snapshot.get(key, {})

            all_fields = set(old_data.keys()) | set(new_data.keys())

            for field in all_fields:
                old_value = old_data.get(field)
                new_value = new_data.get(field)

                old_is_nan = pd.isna(old_value)
                new_is_nan = pd.isna(new_value)

                if old_is_nan and new_is_nan:
                    continue

                if old_value != new_value:
                    changed.append({
                        "key": key,
                        "field": field,
                        "old": old_value,
                        "new": new_value
                    })

        return {'added': added, 'removed': removed, 'changed': changed}

    def run(self):
        logger.info("="*50)
        logger.info("BẮT ĐẦU PHIÊN LÀM VIỆC MỚI")

        active_configs = self.db_manager.get_active_configs()
        if not active_configs:
            logger.warning("Không có cấu hình nào đang hoạt động trong database. Kết thúc.")
            return

        all_individual_results = []
        for config_row in active_configs:
            config = dict(config_row)
            agent_name = config['agent_name']
            project_name = config['project_name']
            config_id = config['id']

            print("="*20)
            print(f"▶️  Đang xử lý: {agent_name} - {project_name} (ID: {config_id})")

            try:
                mappings = self.db_manager.get_column_mappings(config_id)
                downloader = GoogleSheetDownloader(
                    spreadsheet_id=config.get('spreadsheet_id'),
                    html_url=config.get('html_url'),
                    gid=config['gid'],
                    proxies=self.proxies
                )
                current_df, color_df, download_url = downloader.download()

                if current_df is None or color_df is None or current_df.empty:
                    logger.error(f"Không tải được dữ liệu hoặc màu sắc cho ID {config_id}.")
                    continue

                header_info = self._find_header_and_columns(current_df, config, mappings)
                if not header_info:
                    logger.error(f"Không xác định được header/cột cho ID {config_id}.")
                    continue

                new_snapshot = self._extract_snapshot_data(current_df, color_df, header_info, config)

                old_snapshot = self.db_manager.get_latest_snapshot(config_id)

                if old_snapshot is not None:
                    comparison = self._compare_snapshots(new_snapshot, old_snapshot)
                    print(f"    -> So sánh hoàn tất: {len(comparison['added'])} thêm, {len(comparison['removed'])} bán, {len(comparison['changed'])} đổi.")
                else:
                    comparison = {'added': list(new_snapshot.keys()), 'removed': [], 'changed': []}
                    print("    -> Lần đầu chạy, ghi nhận toàn bộ là căn mới.")

                if comparison.get('added') or comparison.get('removed') or comparison.get('changed'):
                    all_individual_results.append({
                        'agent_name': agent_name,
                        'project_name': project_name,
                        'telegram_chat_id': config['telegram_chat_id'],
                        'comparison': comparison
                    })

                self.db_manager.add_snapshot(config_id, new_snapshot)
                print(f"    -> Đã lưu snapshot mới với {len(new_snapshot)} keys.")

            except Exception as e:
                logger.exception(f"Lỗi nghiêm trọng khi xử lý cấu hình ID {config_id}: {e}")
                print(f"    ❌ Lỗi: {e}. Kiểm tra runtime.log để biết chi tiết.")

        print("="*20)
        print("🔄 Đang tổng hợp và gom nhóm kết quả...")
        aggregated_results = defaultdict(lambda: {'added': [], 'removed': [], 'changed': [], 'telegram_chat_id': None})

        for result in all_individual_results:
            key = (result['agent_name'], result['project_name'])

            aggregated_results[key]['added'].extend(result['comparison']['added'])
            aggregated_results[key]['removed'].extend(result['comparison']['removed'])
            aggregated_results[key]['changed'].extend(result['comparison']['changed'])
            if not aggregated_results[key]['telegram_chat_id']:
                aggregated_results[key]['telegram_chat_id'] = result['telegram_chat_id']

        print("🚀 Đang gửi các thông báo tổng hợp...")
        if not self.notifier:
            print("    -> Bỏ qua vì không có BOT_TOKEN.")
            return

        for (agent_name, project_name), data in aggregated_results.items():
            chat_id = data['telegram_chat_id']
            if not chat_id:
                continue

            final_result_for_message = {
                'agent_name': agent_name,
                'project_name': project_name,
                'comparison': {
                    'added': data['added'],
                    'removed': data['removed'],
                    'changed': data['changed']
                }
            }

            message = self.notifier.format_message(final_result_for_message)

            if message:
                print(f"    -> Gửi thông báo cho: {agent_name} - {project_name}")
                self.notifier.send_message(chat_id, message)
                time.sleep(3)

        self.db_manager.close()
        print("="*20)
        print("✅ Hoàn thành tất cả các tác vụ.")


if __name__ == "__main__":
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    proxies = {
        'http': 'http://rb-proxy-apac.bosch.com:8080',
        'https': 'http://rb-proxy-apac.bosch.com:8080'
    }
    if not bot_token:
        print("Lỗi: Vui lòng thiết lập biến môi trường TELEGRAM_BOT_TOKEN.")
    else:
        manager = InventoryScanner(bot_token=bot_token, proxies=None)
        manager.run()
