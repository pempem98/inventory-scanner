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
        self.aligned_results = {}
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
        prefix_list = self.workflow_config.get('project_prefix', {})

        def get_project_name_from_keys(key: str, prefix_list: Dict[str, str]) -> str:
            """Lấy tên dự án từ key bằng cách tìm prefix."""
            for prefix, name in prefix_list.items():
                if key.startswith(prefix):
                    return name
            return 'Unknown'


        for agent_name, projects in self.results.items():
            realign_results = {}
            for _, comparison in projects.items():
                added = comparison.get('added', [])
                for key in added:
                    project_name = get_project_name_from_keys(key, prefix_list)
                    if realign_results.get(project_name) is None:
                        realign_results[project_name] = {'added': [], 'removed': [], 'changed': [], 'remaining': []}
                    realign_results[project_name]['added'].append(key)


                removed = comparison.get('removed', [])
                for key in removed:
                    project_name = get_project_name_from_keys(key, prefix_list)
                    if realign_results.get(project_name) is None:
                        realign_results[project_name] = {'added': [], 'removed': [], 'changed': [], 'remaining': []}
                    realign_results[project_name]['removed'].append(key)

                remaining = comparison.get('remaining', [])
                for key in remaining:
                    project_name = get_project_name_from_keys(key, prefix_list)
                    if realign_results.get(project_name) is None:
                        realign_results[project_name] = {'added': [], 'removed': [], 'changed': [], 'remaining': []}
                    realign_results[project_name]['remaining'].append(key)

                changed = comparison.get('changed', [])
                for change in changed:
                    project_name = get_project_name_from_keys(change['key'], prefix_list)
                    if realign_results.get(project_name) is None:
                        realign_results[project_name] = {'added': [], 'removed': [], 'changed': [], 'remaining': []}
                    realign_results[project_name]['changed'].extend(
                        [
                            {
                                'key': change['key'],
                                'column': col,
                                'before': values['old'],
                                'after': values['new'],
                            }
                            for change in comparison.get('changed', [])
                            for col, values in change['changes'].items()
                        ]
                    )

            for project_name, comparison in realign_results.items():
                converted_results.append({
                    'agent_name': agent_name,
                    'project_name': project_name,
                    'comparison': comparison,
                    'message': comparison.get('message', ''),
                    'url': comparison.get('url', '').replace('htmlview', 'edit'),
                })
        return converted_results

    def _create_detail_sheet(self, results: List[Dict[str, Any]]) -> pd.DataFrame:
        """Tạo DataFrame cho sheet chi tiết với dạng bảng, gộp dự án theo tên ngắn từ key."""
        data = []
        columns = ['Đại lý', 'Dự án', 'Thêm mới', 'Loại bỏ', 'Thay đổi']
        grouped_results = {}

        for result in results:
            agent_name = result.get('agent_name') or 'Unknown'
            project_name = result.get('project_name') or 'Unknown'
            comparison = result.get('comparison') or {'added': [], 'removed': [], 'changed': []}

            group_key = (agent_name, project_name)
            if group_key not in grouped_results:
                grouped_results[group_key] = {
                    'added': comparison.get('added') or [],  # Danh sách các key mới thêm
                    'removed': comparison.get('removed') or [],  # Danh sách các key đã loại bỏ
                    'changed': comparison.get('changed') or []  # Danh sách các thay đổi
                }

        for (agent_name, project_name), info in grouped_results.items():
            added_lines = []
            removed_lines = []
            changed_lines = []

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
                'Dự án': project_name,
                'Thêm mới': "\n".join(added_lines),
                'Loại bỏ': "\n".join(removed_lines),
                'Thay đổi': "\n".join(changed_lines)
            }
            if project_name == 'Unknown':
                continue
            data.append(row)

        return pd.DataFrame(data, columns=columns)

    def _create_json_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tạo dữ liệu báo cáo JSON, gộp dự án theo tên ngắn từ key."""
        grouped_results = {}

        for result in results:
            agent_name = result.get('agent_name') or 'Unknown'
            project_name = result.get('project_name') or 'Unknown'
            comparison = result.get('comparison') or {'added': [], 'removed': [], 'changed': []}

            group_key = (agent_name, project_name)
            if group_key not in grouped_results:
                grouped_results[group_key] = {
                    'added': set(),
                    'removed': set(),
                    'changed': []
                }

            added = comparison.get('added') or []
            removed = comparison.get('removed') or []
            changed = comparison.get('changed') or []
            grouped_results[group_key]['added'].update([str(item) for item in added if item and len(item) > 0])
            grouped_results[group_key]['removed'].update([str(item) for item in removed if item and len(item) > 0])
            grouped_results[group_key]['changed'].extend([item for item in changed if item is not None])

        details_data = []
        for (agent_name, project_name), info in grouped_results.items():
            detail_entry = {
                'agent_name': agent_name,
                'project_name': project_name,
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
        self.aligned_results = converted_results

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
                    adjusted_width = min(max(max_length + 2, 20), 50)
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
