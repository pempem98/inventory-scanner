import json
import os
from datetime import datetime
import logging
import pandas as pd
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any

class ReportGenerator:
    """Class để tạo báo cáo Excel và JSON từ kết quả workflow."""

    def __init__(self, workflow_config_file: str = 'workflow_config.json', report_dir: str = 'report'):
        """
        Khởi tạo ReportGenerator.

        Args:
            workflow_config_file: Đường dẫn đến file workflow config chứa project_prefix.
            report_dir: Thư mục lưu file báo cáo (mặc định là thư mục 'report').
        """
        self.workflow_config_file = workflow_config_file
        self.report_dir = report_dir
        self.workflow_config = self._load_workflow_config()

        # Đảm bảo thư mục báo cáo tồn tại
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            logging.info(f"Đã tạo thư mục báo cáo {report_dir}.")

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

    def _create_summary_sheet(self, results: List[Dict[str, Any]]) -> pd.DataFrame:
        """Tạo DataFrame cho sheet tổng quan."""
        project_prefix = self.workflow_config.get('project_prefix', {}) or {}
        columns = ['Đại lý'] + [f"Dự án {name}" for name in project_prefix.values()]
        data = {}

        for result in results:
            # Kiểm tra NoneType
            agent_name = result.get('agent_name') or 'Unknown'
            project_name = result.get('project_name') or 'Unknown'
            status = result.get('status') or 'N/A'

            if agent_name not in data:
                data[agent_name] = {'Đại lý': agent_name}
                for project_name_col in project_prefix.values():
                    data[agent_name][f"Dự án {project_name_col}"] = 'N/A'

            for prefix, project_name_col in project_prefix.items():
                if project_name.startswith(prefix):
                    data[agent_name][f"Dự án {project_name_col}"] = status
                    break

        return pd.DataFrame(list(data.values()), columns=columns)

    def _get_project_name_from_keys(self, comparison: Dict[str, Any], project_prefix: Dict[str, str]) -> str:
        """Xác định tên dự án ngắn từ prefix trong key của added, removed, changed."""
        if not comparison:
            return 'Unknown'

        added = comparison.get('added') or []
        removed = comparison.get('removed') or []
        changed = comparison.get('changed') or []

        # Kiểm tra tất cả key để tìm prefix
        keys = []
        keys.extend([str(item) for item in added if item is not None])
        keys.extend([str(item) for item in removed if item is not None])
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

        # Nhóm dữ liệu theo agent_name và tên dự án ngắn từ key
        for result in results:
            # Kiểm tra NoneType
            agent_name = result.get('agent_name') or 'Unknown'
            status = result.get('status') or 'N/A'
            comparison = result.get('comparison') or {'added': [], 'removed': [], 'changed': []}

            # Xác định tên dự án từ key
            short_project_name = self._get_project_name_from_keys(comparison, project_prefix)

            # Tạo key để nhóm
            group_key = (agent_name, short_project_name)
            if group_key not in grouped_results:
                grouped_results[group_key] = {
                    'status': 'Success',
                    'added': set(),
                    'removed': set(),
                    'changed': []
                }

            # Kiểm tra trạng thái
            if status != 'Success':
                grouped_results[group_key]['status'] = 'N/A'
            else:
                added = comparison.get('added') or []
                removed = comparison.get('removed') or []
                changed = comparison.get('changed') or []
                grouped_results[group_key]['added'].update([str(item) for item in added if item is not None])
                grouped_results[group_key]['removed'].update([str(item) for item in removed if item is not None])
                grouped_results[group_key]['changed'].extend([item for item in changed if item is not None])

        # Tạo dữ liệu cho DataFrame
        for (agent_name, short_project_name), info in grouped_results.items():
            added_lines = []
            removed_lines = []
            changed_lines = []

            if info['status'] != 'Success':
                added_lines.append("N/A")
                removed_lines.append("N/A")
                changed_lines.append("N/A")
            else:
                added = info['added']
                removed = info['removed']
                changed = info['changed']

                if added:
                    added_lines.extend([f"- {key}" for key in sorted(added)])
                else:
                    added_lines.append("- No update")

                if removed:
                    removed_lines.extend([f"- {key}" for key in sorted(removed)])
                else:
                    removed_lines.append("- No update")

                if changed:
                    for change in changed:
                        key = change.get('key') or 'Unknown'
                        col = change.get('column') or 'Unknown'
                        before = change.get('before', 'Unknown')
                        after = change.get('after', 'Unknown')
                        changed_lines.append(f"- {key}: {col}: {before} -> {after}")
                else:
                    changed_lines.append("- No update")

            # Tạo hàng dữ liệu
            row = {
                'Đại lý': agent_name,
                'Dự án': short_project_name,
                'Thêm mới': "\n".join(added_lines),
                'Loại bỏ': "\n".join(removed_lines),
                'Thay đổi': "\n".join(changed_lines)
            }
            data.append(row)

        return pd.DataFrame(data, columns=columns)

    def _create_json_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tạo dữ liệu báo cáo JSON, gộp dự án theo tên ngắn từ key."""
        project_prefix = self.workflow_config.get('project_prefix', {}) or {}
        summary_data = {}
        grouped_results = {}

        # Tạo dữ liệu tổng quan
        for result in results:
            agent_name = result.get('agent_name') or 'Unknown'
            project_name = result.get('project_name') or 'Unknown'
            status = result.get('status') or 'N/A'

            if agent_name not in summary_data:
                summary_data[agent_name] = {'agent_name': agent_name}
                for project_name_col in project_prefix.values():
                    summary_data[agent_name][f"Dự án {project_name_col}"] = 'N/A'

            for prefix, project_name_col in project_prefix.items():
                if project_name.startswith(prefix):
                    summary_data[agent_name][f"Dự án {project_name_col}"] = status
                    break

        # Nhóm dữ liệu chi tiết
        for result in results:
            agent_name = result.get('agent_name') or 'Unknown'
            status = result.get('status') or 'N/A'
            comparison = result.get('comparison') or {'added': [], 'removed': [], 'changed': []}

            # Xác định tên dự án từ key
            short_project_name = self._get_project_name_from_keys(comparison, project_prefix)

            # Tạo key để nhóm
            group_key = (agent_name, short_project_name)
            if group_key not in grouped_results:
                grouped_results[group_key] = {
                    'status': 'Success',
                    'added': set(),
                    'removed': set(),
                    'changed': []
                }

            # Kiểm tra trạng thái
            if status != 'Success':
                grouped_results[group_key]['status'] = 'N/A'
            else:
                added = comparison.get('added') or []
                removed = comparison.get('removed') or []
                changed = comparison.get('changed') or []
                grouped_results[group_key]['added'].update([str(item) for item in added if item is not None])
                grouped_results[group_key]['removed'].update([str(item) for item in removed if item is not None])
                grouped_results[group_key]['changed'].extend([item for item in changed if item is not None])

        # Tạo dữ liệu chi tiết
        details_data = []
        for (agent_name, short_project_name), info in grouped_results.items():
            detail_entry = {
                'agent_name': agent_name,
                'project_name': short_project_name,
                'status': info['status']
            }
            if info['status'] != 'Success':
                detail_entry.update({
                    'added': None,
                    'removed': None,
                    'changed': None
                })
            else:
                detail_entry.update({
                    'added': sorted(list(info['added'])),
                    'removed': sorted(list(info['removed'])),
                    'changed': info['changed']
                })
            details_data.append(detail_entry)

        return {
            'summary': list(summary_data.values()),
            'details': details_data
        }

    def generate_report(self, results: List[Dict[str, Any]]) -> None:
        """Tạo báo cáo Excel và JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_file = os.path.join(self.report_dir, f"report_{timestamp}.xlsx")
        json_file = os.path.join(self.report_dir, f"report_{timestamp}.json")

        # Kiểm tra results không phải None
        if results is None:
            results = []

        # Tạo sheet tổng quan
        df_summary = self._create_summary_sheet(results)

        # Tạo sheet chi tiết
        df_detail = self._create_detail_sheet(results)

        # Tạo file Excel
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Ghi sheet tổng quan
            df_summary.to_excel(writer, sheet_name='Tổng quan', index=False)

            # Ghi sheet chi tiết
            df_detail.to_excel(writer, sheet_name='Chi tiết', index=False)

            # Điều chỉnh độ rộng cột
            workbook = writer.book
            for sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
                for col in worksheet.columns:
                    max_length = 0
                    column = col[0].column_letter
                    for cell in col:
                        try:
                            if cell.value:
                                max_length = max(max_length, len(str(cell.value)))
                        except:
                            pass
                    adjusted_width = max_length + 2
                    worksheet.column_dimensions[column].width = adjusted_width

        logging.info(f"Đã tạo báo cáo Excel tại {excel_file}")

        # Tạo và lưu file JSON
        json_report = self._create_json_report(results)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        logging.info(f"Đã tạo báo cáo JSON tại {json_file}")

if __name__ == "__main__":
    # Thiết lập logging cơ bản cho ví dụ
    logging.basicConfig(
        filename='report_generator.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )

    # Dữ liệu giả lập mô phỏng kết quả từ WorkflowManager
    example_results = [
        {
            'agent_name': 'ATD',
            'project_name': 'C3_LSB',
            'status': 'Success',
            'comparison': {
                'added': ['C3_Product_001'],
                'removed': [],
                'changed': [
                    {'key': 'C3_Product_002', 'column': 'Quantity', 'before': 100, 'after': 150}
                ]
            }
        },
        {
            'agent_name': 'ATD',
            'project_name': 'C7_LSB',
            'status': 'Success',
            'comparison': {
                'added': ['C3_Product_003'],
                'removed': ['C3_Product_004'],
                'changed': []
            }
        },
        {
            'agent_name': 'ATD',
            'project_name': 'C4_MGA',
            'status': 'Success',
            'comparison': {
                'added': ['C4_Product_005'],
                'removed': [],
                'changed': []
            }
        },
        {
            'agent_name': 'XYZ',
            'project_name': 'C5_MLS',
            'status': 'Failed',
            'comparison': None
        }
    ]

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
    report_generator = ReportGenerator(workflow_config_file='workflow_config.json')
    report_generator.generate_report(example_results)