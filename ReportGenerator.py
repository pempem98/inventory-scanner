import json
import os
from datetime import datetime
import logging
import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment
from typing import List, Dict, Any

# Thiết lập logging
logging.basicConfig(
    filename='runtime.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class ReportGenerator:
    """Class để tạo báo cáo Excel và JSON từ kết quả workflow."""

    def __init__(self, results: Dict[str, Dict[str, Dict[str, List]]], output_dir: str = 'reports', workflow_config_file: str = 'workflow_config.json'):
        """
        Khởi tạo ReportGenerator.

        Args:
            results: Dictionary chứa kết quả so sánh {agent_name: {project_name: {added, removed, changed, remaining}}}.
            output_dir: Thư mục lưu file báo cáo (mặc định là thư mục 'reports').
            workflow_config_file: Đường dẫn đến file workflow config chứa project_prefix.
        """
        self.results = results
        self.output_dir = output_dir
        self.workflow_config_file = workflow_config_file
        self.workflow_config = self._load_workflow_config()

        # Đảm bảo thư mục báo cáo tồn tại
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Đã tạo thư mục báo cáo {output_dir}.")

    def _load_workflow_config(self) -> Dict[str, Any]:
        """Đọc file workflow config."""
        default_config = {'project_prefix': {}}
        try:
            if os.path.exists(self.workflow_config_file):
                with open(self.workflow_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    raise ValueError("File workflow config phải là dictionary.")
                config.setdefault('project_prefix', {})
                return config
            logging.warning(f"File {self.workflow_config_file} không tồn tại, dùng config mặc định.")
            return default_config
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {self.workflow_config_file}: {e}, dùng config mặc định.")
            return default_config

    def _convert_results_format(self) -> List[Dict[str, Any]]:
        """Chuyển đổi results từ dictionary lồng nhau sang danh sách để tương thích với các phương thức hiện tại."""
        converted_results = []
        project_prefix = self.workflow_config.get('project_prefix', {})

        for agent_name, projects in self.results.items():
            for project_name, comparison in projects.items():
                status = 'Success' if any(comparison.get(key, []) for key in ['added', 'removed', 'changed', 'remaining']) else 'Failed'

                formatted_comparison = {
                    'added': comparison.get('added', []),
                    'removed': comparison.get('removed', []),
                    'changed': [
                        {
                            'key': change['key'],
                            'column': col,
                            'before': values['old'],
                            'after': values['new']
                        }
                        for change in comparison.get('changed', [])
                        for col, values in change['changes'].items()
                    ]
                }

                converted_results.append({
                    'agent_name': agent_name,
                    'project_name': project_name,
                    'status': status,
                    'comparison': formatted_comparison
                })

        return converted_results

    def _get_project_name_from_keys(self, comparison: Dict[str, Any], project_prefix: Dict[str, str]) -> str:
        """Xác định tên dự án ngắn từ prefix trong key của added, removed, changed."""
        if not comparison:
            return 'Unknown'

        added = comparison.get('added') or []
        removed = comparison.get('removed') or []
        changed = comparison.get('changed') or []

        keys = []
        keys.extend([str(item) for item in added if item and len(item) > 0])
        keys.extend([str(item) for item in removed if item and len(item) > 0])
        keys.extend([str(change.get('key', '')) for change in changed if change and change.get('key') is not None])

        for key in keys:
            for prefix, name in project_prefix.items():
                if key.startswith(prefix):
                    return name

        return 'Unknown'

    def _create_detail_sheet(self, results: List[Dict[str, Any]]) -> pd.DataFrame:
        """Tạo DataFrame cho sheet chi tiết với dạng bảng, gộp dự án theo tên ngắn từ key."""
        project_prefix = self.workflow_config.get('project_prefix', {}) or {}
        data = []
        columns = ['Đại lý', 'Dự án', 'Thêm mới', 'Loại bỏ', 'Thay đổi']
        grouped_results = {}

        for result in results:
            agent_name = result.get('agent_name') or 'Unknown'
            status = result.get('status') or 'N/A'
            comparison = result.get('comparison') or {'added': [], 'removed': [], 'changed': []}

            short_project_name = self._get_project_name_from_keys(comparison, project_prefix)

            group_key = (agent_name, short_project_name)
            if group_key not in grouped_results:
                grouped_results[group_key] = {
                    'status': 'Success',
                    'added': set(),
                    'removed': set(),
                    'changed': []
                }

            if status != 'Success':
                grouped_results[group_key]['status'] = 'N/A'
            else:
                added = comparison.get('added') or []
                removed = comparison.get('removed') or []
                changed = comparison.get('changed') or []
                grouped_results[group_key]['added'].update([str(item) for item in added if item and len(item) > 0])
                grouped_results[group_key]['removed'].update([str(item) for item in removed if item and len(item) > 0])
                grouped_results[group_key]['changed'].extend([item for item in changed if item is not None])

        for (agent_name, short_project_name), info in grouped_results.items():
            added_lines = []
            removed_lines = []
            changed_lines = []

            if info['status'] == 'Failed':
                added_lines.append("N/A")
                removed_lines.append("N/A")
                changed_lines.append("N/A")
            else:
                added = info['added']
                removed = info['removed']
                changed = info['changed']

                if added:
                    added_lines.extend([f"{key}" for key in sorted(added)])
                else:
                    added_lines.append("- No update")

                if removed:
                    removed_lines.extend([f"{key}" for key in sorted(removed)])
                else:
                    removed_lines.append("- No update")

                if changed:
                    for change in changed:
                        key = change.get('key') or 'Unknown'
                        col = change.get('column') or 'Unknown'
                        before = change.get('before', 'Unknown')
                        after = change.get('after', 'Unknown')
                        changed_lines.append(f"{key}: {col}: {before} -> {after}")
                else:
                    changed_lines.append("- No update")

            row = {
                'Đại lý': agent_name,
                'Dự án': short_project_name,
                'Thêm mới': "\n".join(added_lines),
                'Loại bỏ': "\n".join(removed_lines),
                'Thay đổi': "\n".join(changed_lines)
            }
            if short_project_name == 'Unknown':
                continue
            data.append(row)

        return pd.DataFrame(data, columns=columns)

    def _create_json_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tạo dữ liệu báo cáo JSON, gộp dự án theo tên ngắn từ key."""
        project_prefix = self.workflow_config.get('project_prefix', {}) or {}
        grouped_results = {}

        for result in results:
            agent_name = result.get('agent_name') or 'Unknown'
            status = result.get('status') or 'N/A'
            comparison = result.get('comparison') or {'added': [], 'removed': [], 'changed': []}

            short_project_name = self._get_project_name_from_keys(comparison, project_prefix)

            group_key = (agent_name, short_project_name)
            if group_key not in grouped_results:
                grouped_results[group_key] = {
                    'status': 'Success',
                    'added': set(),
                    'removed': set(),
                    'changed': []
                }

            if status != 'Success':
                grouped_results[group_key]['status'] = 'N/A'
            else:
                added = comparison.get('added') or []
                removed = comparison.get('removed') or []
                changed = comparison.get('changed') or []
                grouped_results[group_key]['added'].update([str(item) for item in added if item and len(item) > 0])
                grouped_results[group_key]['removed'].update([str(item) for item in removed if item and len(item) > 0])
                grouped_results[group_key]['changed'].extend([item for item in changed if item is not None])

        details_data = []
        for (agent_name, short_project_name), info in grouped_results.items():
            detail_entry = {
                'agent_name': agent_name,
                'project_name': short_project_name,
                'status': info['status']
            }
            detail_entry.update({
                'added': sorted(list(info['added'])),
                'removed': sorted(list(info['removed'])),
                'changed': info['changed']
            })
            details_data.append(detail_entry)

        return {'details': details_data}

    def generate_report(self) -> str:
        """Tạo báo cáo Excel chỉ với sheet chi tiết và báo cáo JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_file = os.path.join(self.output_dir, f"report_{timestamp}.xlsx")
        json_file = os.path.join(self.output_dir, f"report_{timestamp}.json")

        # Chuyển đổi results sang định dạng danh sách
        converted_results = self._convert_results_format()

        # Tạo sheet chi tiết
        df_detail = self._create_detail_sheet(converted_results)

        # Tạo file Excel
        try:
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                df_detail.to_excel(writer, sheet_name='Chi tiết', index=False)

                # Điều chỉnh định dạng
                workbook = writer.book
                worksheet = workbook['Chi tiết']
                
                # Áp dụng wrap text cho tất cả các ô
                for row in worksheet.iter_rows():
                    for cell in row:
                        cell.alignment = Alignment(wrap_text=True)

                # Điều chỉnh độ rộng cột (tối thiểu 30)
                for col in worksheet.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if cell.value:
                                max_length = max(max_length, len(str(cell.value)))
                        except:
                            pass
                    adjusted_width = max(max_length + 2, 30)
                    worksheet.column_dimensions[column].width = adjusted_width

            logging.info(f"Đã tạo báo cáo Excel tại {excel_file}")
        except Exception as e:
            logging.error(f"Lỗi khi tạo báo cáo Excel: {e}")
            raise

        # Tạo và lưu file JSON
        try:
            json_report = self._create_json_report(converted_results)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_report, f, indent=2, ensure_ascii=False)
            logging.info(f"Đã tạo báo cáo JSON tại {json_file}")
        except Exception as e:
            logging.error(f"Lỗi khi tạo báo cáo JSON: {e}")
            raise

        return excel_file

if __name__ == "__main__":
    # Dữ liệu giả lập mô phỏng kết quả từ WorkflowManager
    example_results = {
        "ATD": {
            "C3_LSB": {
                "added": [["C3_Product_001", "Tòa A", "Mới"]],
                "removed": [],
                "changed": [
                    {"key": "C3_Product_002", "changes": {"Quantity": {"old": 100, "new": 150}}}
                ],
                "remaining": [["C3_Product_003", "Tòa B", "Cũ"]]
            },
            "C7_LSB": {
                "added": [["C3_Product_004", "Tòa C", "Mới"]],
                "removed": [["C3_Product_005", "Tòa D", "Cũ"]],
                "changed": [],
                "remaining": []
            }
        },
        "XYZ": {
            "C5_MLS": {
                "added": [],
                "removed": [],
                "changed": [],
                "remaining": []
            }
        }
    }

    # Giả lập workflow_config.json
    example_config = {
        'project_prefix': {
            'C3': 'LSB',
            'C4': 'MGA',
            'C5': 'MLS'
        }
    }
    with open('workflow_config.json', 'w', encoding='utf-8') as f:
        json.dump(example_config, f, indent=2)

    # Khởi tạo và chạy ReportGenerator
    report_generator = ReportGenerator(results=example_results, workflow_config_file='workflow_config.json')
    report_generator.generate_report()