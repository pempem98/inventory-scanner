import pandas as pd
import os
import json
import logging
import re
from typing import Dict, List, Optional

class ExcelBackupExtractor:
    """Class để trích xuất key và check columns từ file Excel/CSV backup dựa trên project_config.json."""

    def __init__(self, project_config_file: str = 'project_config.json', workflow_config_file: str = 'workflow_config.json'):
        """
        Khởi tạo extractor.

        Args:
            project_config_file: File cấu hình chứa key_column, check_columns, backup_files.
            workflow_config_file: File chứa allowed_key_pattern (nếu project_config.json không có).
        """
        self.project_config_file = project_config_file
        self.workflow_config_file = workflow_config_file
        self.output_dir = 'extracted_data'
        self.results = []
        self.project_config = self.load_project_config()
        self.allowed_key_pattern = self.load_allowed_key_pattern()

        # Thiết lập logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='extract_excel_backup.log',
            encoding='utf-8'
        )

        # Tạo thư mục lưu kết quả
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_project_config(self) -> Dict:
        """Đọc project_config.json."""
        try:
            with open(self.project_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if not isinstance(config, list):  # Điều chỉnh cho cấu trúc danh sách
                raise ValueError("project_config.json phải là danh sách các agent")
            return config
        except Exception as e:
            logging.error(f"Lỗi khi đọc {self.project_config_file}: {e}")
            return []

    def load_allowed_key_pattern(self) -> str:
        """Đọc allowed_key_pattern, ưu tiên project_config.json."""
        try:
            with open(self.project_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            pattern = config.get('allowed_key_pattern')
            if pattern:
                return pattern
        except Exception:
            pass

        try:
            with open(self.workflow_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('allowed_key_pattern', r'^[A-Za-z0-9._-]+$')
        except Exception as e:
            logging.error(f"Lỗi khi đọc {self.workflow_config_file}: {e}")
            return r'^[A-Za-z0-9._-]+$'

    def read_file(self, file_path: str) -> pd.DataFrame:
        """Đọc file Excel hoặc CSV, sử dụng row đầu tiên làm header."""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            if df.empty:
                logging.warning(f"File {file_path} rỗng.")
                return pd.DataFrame()
            return df
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {file_path}: {e}")
            return pd.DataFrame()

    def extract_data(self, df: pd.DataFrame, file_name: str, key_col: str, check_cols: List[str], agent_name: str, project_name: str) -> List[Dict]:
        """Trích xuất key và check columns từ DataFrame dựa trên header."""
        try:
            if df.empty:
                logging.warning(f"DataFrame rỗng cho file {file_name}.")
                return []

            # Kiểm tra header
            headers = df.columns.tolist()
            if key_col not in headers:
                logging.warning(f"Cột key '{key_col}' không tồn tại trong {file_name}. Headers: {headers}")
                return []

            # Kiểm tra check_cols
            valid_check_cols = [col for col in check_cols if col in headers]
            missing_cols = [col for col in check_cols if col not in headers]
            if missing_cols:
                logging.warning(f"Các cột check không tồn tại trong {file_name}: {missing_cols}")

            # Lọc key hợp lệ
            df['key'] = df[key_col].astype(str)
            valid_mask = (
                df['key'].str.match(self.allowed_key_pattern) &
                (df['key'] != '') &
                (df['key'] != 'nan') &
                df['key'].notna()
            )

            invalid_keys = df[~valid_mask]['key'].dropna().tolist()
            if invalid_keys:
                logging.info(f"Đã bỏ qua key không hợp lệ trong {file_name}: {invalid_keys}")

            df_valid = df[valid_mask]
            if df_valid.empty:
                logging.warning(f"Không có key hợp lệ trong {file_name}.")
                return []

            data = []
            for _, row in df_valid.iterrows():
                entry = {
                    'file': file_name,
                    'agent': agent_name,
                    'project': project_name,
                }
                check_key = f'{agent_name}_{project_name}_{key_col}'
                entry[check_key] = row[key_col]
                for col_name in valid_check_cols:
                    data_key = f'{agent_name}_{project_name}_{col_name}'
                    value = row[col_name]
                    entry[data_key] = 'Unknown' if pd.isna(value) else value
                data.append(entry)
            return data
        except Exception as e:
            logging.error(f"Lỗi khi trích xuất dữ liệu từ {file_name}: {e}")
            return []

    def process_backups(self, folder_path="predecessor"):
        """Trích xuất dữ liệu từ tất cả file backup trong project_config.json."""
        backup_files = []
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for root, _, files in os.walk(folder_path):
                for file in files:
                    backup_files.append(os.path.join(root, file))

        for agent in self.project_config:
            agent_name = agent.get('agent_name', 'Unknown')
            for project in agent.get('configs', []):
                project_name = project.get('project_name', 'Unknown')
                key_col = project.get('key_column', 'MÃ CĂN')
                check_cols = project.get('check_columns', ['Quantity'])

                for file_path in backup_files:
                    if not os.path.exists(file_path):
                        logging.warning(f"File {file_path} không tồn tại.")
                        continue
                    if not f"{agent_name}_{project_name}" in file_path:
                        continue

                    logging.info(f"Đang xử lý file {file_path}")
                    df = self.read_file(file_path)
                    if not df.empty:
                        file_data = self.extract_data(
                            df=df,
                            file_name=os.path.basename(file_path),
                            key_col=key_col,
                            check_cols=check_cols,
                            agent_name=agent_name,
                            project_name=project_name
                        )
                        self.results.extend(file_data)

    def save_results(self):
        """Lưu kết quả vào file JSON."""
        output_file = os.path.join(self.output_dir, 'extracted_backup_data.json')
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            logging.info(f"Đã lưu kết quả vào {output_file}")
        except Exception as e:
            logging.error(f"Lỗi khi lưu kết quả: {e}")

    def print_results(self):
        """In kết quả ra console."""
        print("\n=== Kết quả trích xuất ===")
        for entry in self.results:
            print(entry)
            print("-" * 30)

def main():
    # Khởi tạo và chạy extractor
    extractor = ExcelBackupExtractor(
        project_config_file='project_config.json',
        workflow_config_file='workflow_config.json'
    )

    extractor.process_backups(folder_path="current")
    extractor.print_results()
    extractor.save_results()

if __name__ == "__main__":
    main()