import os
import json
import time
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Import các module đã được tùy chỉnh
from DatabaseManager import DatabaseManager
from GoogleSheetDownloader import GoogleSheetDownloader
from TelegramNotifier import TelegramNotifier

# Thiết lập logging
logging.basicConfig(
    filename='runtime.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class WorkflowManager:
    """
    Quản lý luồng công việc chính: tải, so sánh, và thông báo dữ liệu
    dựa trên cấu hình từ cơ sở dữ liệu SQLite.
    """

    def __init__(self, bot_token: str, proxies: Optional[Dict[str, str]] = None):
        """
        Khởi tạo WorkflowManager.

        Args:
            bot_token: Token của bot Telegram để sử dụng cho việc thông báo.
            proxies: Cấu hình proxy (nếu có).
        """
        self.db_manager = DatabaseManager()
        self.proxies = proxies
        # Khởi tạo Notifier một lần để tái sử dụng
        if bot_token:
            self.notifier = TelegramNotifier(bot_token=bot_token, proxies=self.proxies)
        else:
            self.notifier = None
            logging.warning("Không có BOT_TOKEN, sẽ không có thông báo nào được gửi.")

    def _find_header_and_columns(self, df: pd.DataFrame, config: dict) -> Optional[Dict[str, Any]]:
        """
        Tự động tìm hàng header và vị trí các cột quan trọng dựa vào cấu hình.
        """
        key_col_aliases = [key.lower() for key in json.loads(config.get('key_column_aliases', '[]'))]
        price_col_aliases = [key.lower() for key in json.loads(config.get('price_column_aliases', '[]'))]
        if not key_col_aliases:
            logging.error(f"Dự án {config['project_name']} không có 'key_column_aliases' được cấu hình.")
            return None

        header_row_idx = -1

        # Ưu tiên 1: Lấy chỉ số hàng được cấu hình sẵn
        config_header_idx = config.get('header_row_index')
        if config_header_idx and 0 < config_header_idx <= len(df):
            header_row_idx = config_header_idx - 1
        else:
            # Ưu tiên 2: Tự động quét 10 dòng đầu tiên để tìm header
            for i, row in df.head(10).iterrows():
                row_values = {str(val).strip().lower() for val in row.dropna().values}
                if not set(key_col_aliases).isdisjoint(row_values):
                    header_row_idx = i
                    break
        
        if header_row_idx == -1:
            logging.error(f"Không thể tự động tìm thấy hàng header cho dự án {config['project_name']}.")
            return None
        
        header_content = [str(h).strip().lower() for h in df.iloc[header_row_idx].tolist()]

        # Tìm vị trí cột khóa
        key_col_idx = None
        for alias in key_col_aliases:
            try:
                key_col_idx = header_content.index(alias)
                break
            except ValueError:
                continue
        
        if key_col_idx is None:
            logging.error(f"Không tìm thấy cột khóa nào cho dự án {config['project_name']}.")
            return None

        # --- [MỚI] Tìm cột giá (price) ---
        price_col_idx = None # Cột giá có thể không bắt buộc
        if price_col_aliases:
            for alias in price_col_aliases:
                try:
                    price_col_idx = header_content.index(alias)
                    break
                except ValueError:
                    continue
        
        if price_col_idx is None:
            logging.warning(f"Không tìm thấy cột giá cho dự án {config['project_name']}. Bỏ qua việc theo dõi giá.")

        logging.info(f"Đã xác định header ở dòng {header_row_idx + 1}. Cột khóa ở vị trí {key_col_idx}, Cột giá ở vị trí {price_col_idx}.")

        # --- [MỚI] Trả về cả price_col_idx ---
        return {
            "header_row_idx": header_row_idx,
            "key_col_idx": key_col_idx,
            "price_col_idx": price_col_idx,
            "header": header_content
        }

    def _normalize_and_validate_key(self, key: Any, prefixes: Optional[List[str]]) -> Optional[str]:
        """Làm sạch và kiểm tra key có hợp lệ với các tiền tố đã cho không."""
        if not isinstance(key, (str, int, float)):
            return None
        
        clean_key = str(key).strip().upper()
        if not clean_key:
            return None
        
        if not prefixes:
            return clean_key # Nếu không cấu hình prefix, mọi key đều hợp lệ

        for prefix in prefixes:
            if clean_key.startswith(prefix.upper()):
                return clean_key
        
        return None # Key không hợp lệ

    def _extract_snapshot_data(self, data_df: pd.DataFrame, color_df: pd.DataFrame, header_info: dict, config: dict) -> Dict[str, Any]:
        """
        Trích xuất dữ liệu snapshot từ DataFrame, có kiểm tra màu sắc không hợp lệ.
        """
        snapshot_data = {}
        key_col_idx = header_info['key_col_idx']
        price_col_idx = header_info['price_col_idx']
        
        # Lấy cấu hình màu không hợp lệ từ DB
        invalid_colors_json = config.get('invalid_colors', '[]')
        invalid_colors = {c.lower() for c in json.loads(invalid_colors_json)}

        # Lấy DataFrame chứa dữ liệu và màu sắc thực tế (bỏ các dòng trên header)
        data_rows_df = data_df.iloc[header_info['header_row_idx'] + 1:]
        color_rows_df = color_df.iloc[header_info['header_row_idx'] + 1:]

        # Lấy cấu hình tiền tố
        prefixes_json = config.get('key_prefixes')
        valid_prefixes = json.loads(prefixes_json) if prefixes_json else None

        for index, row in data_rows_df.iterrows():
            raw_key = row.iloc[key_col_idx]
            valid_key = self._normalize_and_validate_key(raw_key, valid_prefixes)

            if valid_key:
                # Kiểm tra màu sắc của ô key
                try:
                    cell_color = color_rows_df.loc[index].iloc[key_col_idx]
                    if cell_color and cell_color.lower() in invalid_colors:
                        logging.info(f"Bỏ qua key '{valid_key}' do có màu không hợp lệ: {cell_color}")
                        continue # Bỏ qua key này và đi đến vòng lặp tiếp theo
                except (KeyError, IndexError):
                    # Bỏ qua nếu không tìm thấy màu tương ứng (ít khi xảy ra)
                    pass

                price_value = None
                if price_col_idx is not None:
                    price_value = row.iloc[price_col_idx]

                # Nếu key hợp lệ và màu hợp lệ, thêm vào snapshot\
                snapshot_data[valid_key] = {
                    "price": price_value
                }

        return snapshot_data

    def _compare_snapshots(self, new_snapshot: Dict, old_snapshot: Dict) -> Dict[str, List]:
        """So sánh hai snapshot, có thể mở rộng để so sánh cả giá."""
        new_keys = set(new_snapshot.keys())
        old_keys = set(old_snapshot.keys())

        added = sorted(list(new_keys - old_keys))
        removed = sorted(list(old_keys - new_keys))
        
        changed = []
        # [MỚI] So sánh giá cho các key chung
        common_keys = new_keys.intersection(old_keys)
        for key in common_keys:
            old_price = old_snapshot[key].get('price')
            new_price = new_snapshot[key].get('price')
            
            # Xử lý trường hợp giá là NaN hoặc None
            old_price_is_nan = pd.isna(old_price)
            new_price_is_nan = pd.isna(new_price)
            
            if old_price_is_nan and new_price_is_nan:
                continue # Cả hai đều không có giá trị, coi như không đổi
            
            if old_price != new_price and not (old_price_is_nan and new_price_is_nan):
                 changed.append({
                    "key": key,
                    "field": "price",
                    "old": old_price,
                    "new": new_price
                 })

        return {'added': added, 'removed': removed, 'changed': changed}

    def run(self):
        """Chạy luồng công việc chính."""
        logging.info("="*50)
        logging.info("BẮT ĐẦU PHIÊN LÀM VIỆC MỚI")
        
        active_configs = self.db_manager.get_active_configs()
        if not active_configs:
            logging.warning("Không có cấu hình nào đang hoạt động trong database. Kết thúc.")
            return

        all_individual_results = []
        for config_row in active_configs:
            config = dict(config_row)
            agent_name = config['agent_name']
            project_name = config['project_name']
            config_id = config['id']
            
            print(f"\n▶️  Đang xử lý: {agent_name} - {project_name} (ID: {config_id})")

            try:
                # 1. Tải dữ liệu từ Google Sheet
                downloader = GoogleSheetDownloader(
                    spreadsheet_id=config.get('spreadsheet_id'),
                    html_url=config.get('html_url'),
                    gid=config['gid'],
                    proxies=self.proxies
                )
                current_df, color_df, download_url = downloader.download()

                if current_df is None or color_df is None or current_df.empty:
                    logging.error(f"Không tải được dữ liệu hoặc màu sắc cho ID {config_id}.")
                    continue

                # 2. Tìm header và các cột quan trọng
                header_info = self._find_header_and_columns(current_df, config)
                if not header_info:
                    logging.error(f"Không xác định được header/cột cho ID {config_id}.")
                    continue
                
                # 3. Trích xuất dữ liệu snapshot hiện tại
                new_snapshot = self._extract_snapshot_data(current_df, color_df, header_info, config)

                # 4. Lấy snapshot cũ và so sánh
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
                logging.exception(f"Lỗi nghiêm trọng khi xử lý cấu hình ID {config_id}: {e}")
                print(f"    ❌ Lỗi: {e}. Kiểm tra runtime.log để biết chi tiết.")

        print("\n🔄 Đang tổng hợp và gom nhóm kết quả...")
        aggregated_results = defaultdict(lambda: {'added': [], 'removed': [], 'changed': [], 'telegram_chat_id': None})

        for result in all_individual_results:
            key = (result['agent_name'], result['project_name'])
            
            aggregated_results[key]['added'].extend(result['comparison']['added'])
            aggregated_results[key]['removed'].extend(result['comparison']['removed'])
            aggregated_results[key]['changed'].extend(result['comparison']['changed'])
            # Lấy chat_id, giả định các cấu hình con của cùng 1 dự án có cùng chat_id
            if not aggregated_results[key]['telegram_chat_id']:
                aggregated_results[key]['telegram_chat_id'] = result['telegram_chat_id']

        # Bước 3: Gửi thông báo tổng hợp
        print("🚀 Đang gửi các thông báo tổng hợp...")
        if not self.notifier:
            print("    -> Bỏ qua vì không có BOT_TOKEN.")
            return

        for (agent_name, project_name), data in aggregated_results.items():
            chat_id = data['telegram_chat_id']
            if not chat_id:
                continue

            # Tạo một dict kết quả tổng hợp để format
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
                time.sleep(1) # Tạm dừng giữa các tin nhắn
        
        self.db_manager.close()
        print("\n✅ Hoàn thành tất cả các tác vụ.")


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
        manager = WorkflowManager(bot_token=bot_token, proxies=None)
        manager.run()