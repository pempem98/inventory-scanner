import numpy as np
import pandas as pd
import re
from typing import List, Dict, Any, Tuple
import logging

class ExcelSnapshotComparator:
    """Class để so sánh hai snapshot Excel, kiểm tra thay đổi dựa trên cột key."""

    def __init__(self, file_predecessor: str, file_current: str, key_col: str, check_cols: List[str], allowed_key_pattern: str = r'^[A-Z0-9._-]+$'):
        """
        Khởi tạo với thông tin file và cột.

        Args:
            file_predecessor: Đường dẫn đến file Excel trước.
            file_current: Đường dẫn đến file Excel hiện tại.
            key_col: Ký hiệu cột làm key (ví dụ: 'A', 'AA').
            check_cols: Danh sách ký hiệu cột cần kiểm tra (ví dụ: ['B', 'C']).
            allowed_key_pattern: Regex cho key hợp lệ.
        """
        self.file_predecessor = file_predecessor
        self.file_current = file_current
        self.key_col = self.excel_col_to_index(key_col)
        self.check_cols = [self.excel_col_to_index(col) for col in check_cols]
        self.allowed_key_pattern = allowed_key_pattern

    @staticmethod
    def excel_col_to_index(col: str) -> int:
        """Chuyển ký hiệu cột Excel thành chỉ số 0-based."""
        if not col or not col.isalpha():
            raise ValueError(f"Ký hiệu cột '{col}' không hợp lệ. Phải là chữ cái (A, B, AA, ...).")
        col = col.upper()
        index = 0
        for char in col:
            index = index * 26 + (ord(char) - ord('A') + 1)
        return index - 1

    def read_excel_file(self, file_path: str) -> pd.DataFrame:
        """Đọc file Excel, trả về DataFrame."""
        try:
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path, header=None)
            else:
                df = pd.read_excel(file_path, header=None)
            if df.empty:
                raise Exception(f"File {file_path} rỗng.")
            return df
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {file_path}: {e}")
            return pd.DataFrame()

    def validate_keys(self, df: pd.DataFrame, file_name: str) -> pd.DataFrame:
        """Lọc các key hợp lệ dựa trên regex."""
        try:
            if df.empty or self.key_col < 0 or self.key_col >= df.shape[1]:
                logging.warning(f"Cột key không tồn tại hoặc file rỗng trong {file_name}.")
                return pd.DataFrame()

            df['key'] = df[self.key_col].astype(str)
            valid_mask = (
                df['key'].str.match(self.allowed_key_pattern) &
                (df['key'] != '') &
                (df['key'] != 'nan') &
                (df['key'].str.len() >= 6) &
                (df['key'].str.len() <= 15) &
                df['key'].notna()
            )

            invalid_keys = df[~valid_mask]['key'].dropna().tolist()
            if invalid_keys:
                logging.info(f"Đã bỏ qua các key không hợp lệ trong {file_name}: {invalid_keys}")

            return df[valid_mask].copy()
        except Exception as e:
            logging.error(f"Lỗi khi lọc key trong {file_name}: {e}")
            return pd.DataFrame()

    def compare_snapshots(self, df_predecessor: pd.DataFrame, df_current: pd.DataFrame) -> Dict[str, Any]:
        """
        So sánh hai snapshot dựa trên cột key và các cột kiểm tra.

        Args:
            df_predecessor: DataFrame của snapshot cũ.
            df_current: DataFrame của snapshot hiện tại.

        Returns:
            Dictionary chứa added, removed, changed.
        """
        try:
            if df_predecessor.empty or df_current.empty:
                logging.warning("Một hoặc cả hai DataFrame rỗng.")
                return {'added': [], 'removed': [], 'changed': []}

            if not self.check_cols or any(c < 0 or c >= df_predecessor.shape[1] or c >= df_current.shape[1] for c in self.check_cols):
                logging.warning("Cột kiểm tra không hợp lệ.")
                return {'added': [], 'removed': [], 'changed': []}

            keys_predecessor = set(df_predecessor['key'])
            keys_current = set(df_current['key'])

            # Sử dụng key gốc (đã chứa prefix như C3_)
            new_keys = list(keys_current - keys_predecessor)
            missing_keys = list(keys_predecessor - keys_current)
            common_keys = keys_predecessor.intersection(keys_current)

            changes = []
            for key in common_keys:
                row_predecessor = df_predecessor[df_predecessor['key'] == key].iloc[0]
                row_current = df_current[df_current['key'] == key].iloc[0]

                for col in self.check_cols:
                    old_value = row_predecessor.get(col, None)
                    new_value = row_current.get(col, None)
                    if pd.isna(old_value) and pd.isna(new_value):
                        continue
                    if old_value != new_value:
                        changes.append({
                            'key': key,
                            'column': self.index_to_excel_col(col),
                            'before': old_value if pd.notnull(old_value) else 'Unknown',
                            'after': new_value if pd.notnull(new_value) else 'Unknown'
                        })

            return {
                'added': new_keys,
                'removed': missing_keys,
                'changed': changes,
                'checking': keys_current
            }
        except Exception as e:
            logging.error(f"Lỗi khi so sánh snapshot: {e}")
            return {'added': [], 'removed': [], 'changed': []}

    @staticmethod
    def index_to_excel_col(index: int) -> str:
        """Chuyển chỉ số cột thành ký hiệu Excel."""
        if index < 0:
            raise ValueError("Chỉ số cột không hợp lệ.")
        col = ''
        while index >= 0:
            col = chr(65 + (index % 26)) + col
            index = index // 26 - 1
        return col

    def print_comparison_results(self, changes: List[Dict[str, Any]], new_keys: List[Any], missing_keys: List[Any]) -> None:
        """In kết quả so sánh."""
        print("\n=== Kết quả so sánh ===")
        if changes:
            print("\nCác thay đổi trong dữ liệu:")
            for change in changes:
                print(f"Key: {change['key']}, Cột: {change['column']}, "
                      f"Giá trị cũ: {change['before']}, Giá trị mới: {change['after']}")
        else:
            print("\nKhông có thay đổi trong các cột kiểm tra.")
        if new_keys:
            print("\nKey mới (chỉ có trong snapshot hiện tại):")
            for key in new_keys:
                print(f"- {key}")
        else:
            print("\nKhông có key mới.")
        if missing_keys:
            print("\nKey bị mất (chỉ có trong snapshot trước):")
            for key in missing_keys:
                print(f"- {key}")
        else:
            print("\nKhông có key bị mất.")
        print("\n=======================")

    def compare(self, project_name: str = 'Unknown') -> Dict[str, Any]:
        """
        Hàm chính: So sánh hai snapshot và trả về kết quả.

        Args:
            project_name: Tên dự án (dùng để tương thích, không ảnh hưởng logic).

        Returns:
            Dictionary chứa added, removed, changed.
        """
        try:
            df_predecessor = self.read_excel_file(self.file_predecessor)
            df_current = self.read_excel_file(self.file_current)
            df_predecessor = self.validate_keys(df_predecessor, self.file_predecessor)
            df_current = self.validate_keys(df_current, self.file_current)

            if df_predecessor.empty or df_current.empty:
                logging.warning("Một hoặc cả hai file không có key hợp lệ để so sánh.")
                self.print_comparison_results([], [], [])
                return {'added': [], 'removed': [], 'changed': []}

            result = self.compare_snapshots(df_predecessor, df_current)
            self.print_comparison_results(result['changed'], result['added'], result['removed'])
            return result
        except Exception as e:
            logging.error(f"Lỗi khi so sánh: {e}")
            self.print_comparison_results([], [], [])
            return {'added': [], 'removed': [], 'changed': []}

# Chạy ví dụ
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    comparator = ExcelSnapshotComparator(
        file_predecessor='./predecessor/NewstarLand_MLS.csv',
        file_current='./current/NewstarLand_MLS.csv',
        key_col='B',
        check_cols=['F'],
        allowed_key_pattern='^[A-Za-z0-9_.-]+$'
    )
    result = comparator.compare(project_name='C3_LSB')
    print(result)