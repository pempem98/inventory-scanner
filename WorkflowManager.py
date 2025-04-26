import json
import os
import shutil
import time
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional, Tuple
from AgentConfig import AgentConfig
from GoogleSheetDownloader import GoogleSheetDownloader
from ExcelSnapshotComparator import ExcelSnapshotComparator
from ReportGenerator import ReportGenerator
from TelegramNotifier import TelegramNotifier

# Thiết lập logging
logging.basicConfig(
    filename='runtime.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class WorkflowManager:
    """Quản lý workflow tải Google Sheet và so sánh snapshot."""

    def __init__(
        self,
        config_file: str,
        workflow_config_file: str = 'workflow_config.json',
        predecessor_dir: str = 'predecessor',
        current_dir: str = 'current',
        backup_dir: str = 'backup',
        proxies: Optional[Dict[str, str]] = None
    ):
        self.config_file = config_file
        self.workflow_config_file = workflow_config_file
        self.predecessor_dir = predecessor_dir
        self.current_dir = current_dir
        self.backup_dir = backup_dir
        self.proxies = proxies
        self.configs = AgentConfig.load_from_json(config_file)
        self.workflow_config = self._load_workflow_config()

        # Kiểm tra cấu trúc self.configs
        if not isinstance(self.configs, list) or not all(hasattr(item, 'agent_name') and hasattr(item, 'configs') for item in self.configs):
            logging.error(f"Cấu trúc self.configs không hợp lệ: {self.configs}")
            raise ValueError("self.configs phải là danh sách các AgentConfig với agent_name và configs")

        # Kiểm tra proxy
        if self.proxies:
            logging.info(f"Sử dụng proxy: {self.proxies}")
        else:
            logging.info("Không sử dụng proxy")

        # Tạo các thư mục nếu chưa tồn tại
        for directory in [self.predecessor_dir, self.current_dir, self.backup_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logging.info(f"Đã tạo thư mục {directory}.")

    def _load_workflow_config(self) -> Dict[str, Any]:
        """Đọc file config workflow."""
        default_config = {
            'allowed_key_pattern': r'^[A-Za-z0-9_.-]+$',
            'snapshot_extension': '.xlsx',
            'project_prefix': {},
            'telegram': {}
        }
        try:
            if os.path.exists(self.workflow_config_file):
                with open(self.workflow_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    raise ValueError("File workflow config phải là dictionary.")
                config.setdefault('project_prefix', {})
                config.setdefault('telegram', {})
                return config
            logging.warning(f"File {self.workflow_config_file} không tồn tại, dùng config mặc định.")
            return default_config
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {self.workflow_config_file}: {e}, dùng config mặc định.")
            return default_config

    def _get_file_name(self, agent_name: str, config: AgentConfig.Config, directory: str) -> str:
        """Tạo tên file theo định dạng {agent_name}_{project_name}.xlsx."""
        clean_project_name = config.project_name.replace(' ', '_')
        file_extension = self.workflow_config.get('snapshot_extension', '.xlsx')
        file_name = f"{agent_name}_{clean_project_name}{file_extension}"
        return os.path.join(directory, file_name)

    def _find_predecessor_file(self, agent_name: str, config: AgentConfig.Config) -> str:
        """Tìm file predecessor trong thư mục predecessor."""
        file_path = self._get_file_name(agent_name, config, self.predecessor_dir)
        if os.path.exists(file_path):
            logging.info(f"Tìm thấy file predecessor: {file_path} cho {agent_name}/{config.project_name}")
            return file_path
        return ''

    def _backup_predecessor_files(self) -> None:
        """Sao lưu tất cả file trong thư mục predecessor vào backup với dấu thời gian."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_subdir = os.path.join(self.backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_subdir, exist_ok=True)

        for file_name in os.listdir(self.predecessor_dir):
            src_path = os.path.join(self.predecessor_dir, file_name)
            if os.path.isfile(src_path):
                dst_path = os.path.join(backup_subdir, file_name)
                shutil.copy2(src_path, dst_path)
                logging.info(f"Đã sao lưu {src_path} vào {dst_path}")

    def _copy_current_to_predecessor(self) -> None:
        """Sao chép tất cả file từ current sang predecessor, xóa file đã sao chép."""
        copied_files = []
        for file_name in os.listdir(self.current_dir):
            src_path = os.path.join(self.current_dir, file_name)
            if os.path.isfile(src_path):
                dst_path = os.path.join(self.predecessor_dir, file_name)
                shutil.copy2(src_path, dst_path)
                logging.info(f"Đã sao chép {src_path} sang {dst_path} (ghi đè nếu tồn tại)")
                copied_files.append(src_path)

        for file_path in copied_files:
            os.remove(file_path)
            logging.info(f"Đã xóa {file_path}")

        if not os.listdir(self.current_dir):
            logging.info(f"Thư mục {self.current_dir} đã trống sau khi sao chép")
        else:
            logging.warning(f"Thư mục {self.current_dir} vẫn còn file sau khi sao chép: {os.listdir(self.current_dir)}")

    def _download_snapshot(self, agent_name: str, config: AgentConfig.Config) -> Tuple[str, str]:
        """Tải Google Sheet và lưu snapshot vào thư mục current."""
        start_time = time.time()
        file_name = self._get_file_name(agent_name, config, self.current_dir)

        logging.info(f"Bắt đầu tải snapshot cho {agent_name}/{config.project_name}")
        print(f"Đại lý {agent_name} - Dự án {config.project_name}")

        downloader = GoogleSheetDownloader(
            spreadsheet_id=config.spreadsheet_id,
            html_url=config.html_url,
            gid=config.gid,
            proxies=self.proxies
        )
        download_url = downloader.download(output_file=file_name)

        if not os.path.exists(file_name):
            logging.error(f"Không tạo được file snapshot {file_name} cho {agent_name}/{config.project_name}")
            return '', ''

        logging.info(f"Đã tải snapshot {file_name} cho {agent_name}/{config.project_name} trong {time.time() - start_time:.2f}s")
        return file_name, download_url

    def _compare_snapshots(self, agent_name: str, config: AgentConfig.Config) -> Dict[str, List]:
        """So sánh file current với predecessor."""
        start_time = time.time()
        current_file = self._get_file_name(agent_name, config, self.current_dir)
        predecessor_file = self._find_predecessor_file(agent_name, config)
        result = {'added': [], 'removed': [], 'changed': [], 'remaining': []}

        logging.info(f"Bắt đầu so sánh snapshot cho {agent_name}/{config.project_name}")

        if not os.path.exists(current_file):
            logging.error(f"File current {current_file} không tồn tại.")
            result['message'] = f"[Warning] Bản ghi mới {current_file} không tồn tại."
            return result

        if not predecessor_file:
            message = f"Không tìm thấy bản ghi cũ cho {agent_name}/{config.project_name}. Bỏ qua so sánh."
            logging.info(message)
            result['message'] = f"[Warning] {message}"
            return result

        comparator = ExcelSnapshotComparator(
            file_predecessor=predecessor_file,
            file_current=current_file,
            key_col=config.key_column,
            check_cols=config.check_columns,
            allowed_key_pattern=self.workflow_config.get('allowed_key_pattern', r'^[A-Za-z0-9_.-]+$'),
            valid_colors=config.valid_colors,
        )
        result = comparator.compare()
        logging.info(f"Kết quả so sánh cho {agent_name}/{config.project_name} trong {time.time() - start_time:.2f}s: {result}")
        return result

    def run(self) -> Dict[str, Dict[str, Dict[str, List]]]:
        """Chạy workflow: tải snapshot, so sánh, tạo báo cáo và gửi thông báo."""
        start_time = time.time()
        results = {}

        logging.info("Bắt đầu chạy workflow")

        # Sao lưu và cập nhật predecessor
        self._backup_predecessor_files()
        self._copy_current_to_predecessor()

        # Tải snapshot cho tất cả đại lý
        for item in self.configs:
            try:
                if not hasattr(item, 'agent_name') or not hasattr(item, 'configs'):
                    logging.error(f"Đối tượng config không hợp lệ: {item}")
                    continue
                agent_name, agent_configs = item.agent_name, item.configs
                results[agent_name] = {}
                for config in agent_configs:
                    logging.info(f"Xử lý {agent_name}/{config.project_name}")
                    snapshot_file, download_url = self._download_snapshot(agent_name, config)
                    if snapshot_file:
                        result = self._compare_snapshots(agent_name, config)
                    else:
                        result = {'message': f"[Error] Không tải được bản ghi cho {agent_name}/{config.project_name}"}
                        result.update({'added': [], 'removed': [], 'changed': [], 'remaining': []})
                    result['url'] = download_url
                    results[agent_name][config.project_name] = result
            except Exception as e:
                logging.error(f"Lỗi khi xử lý đại lý {agent_name}: {e}")
                continue

        # Tạo báo cáo
        report_generator = ReportGenerator(
            results=results,
            workflow_config_file=self.workflow_config_file,
            output_dir='reports'
        )
        report_file = report_generator.generate_report()

        # Gửi thông báo Telegram
        aligned_results = report_generator.aligned_results
        telegram_config = self.workflow_config.get('telegram', {})
        if telegram_config.get('bot_token') and telegram_config.get('chat_id'):
            notifier = TelegramNotifier(
                workflow_config=self.workflow_config,
            )
            notifier.notify(aligned_results, report_file)
        else:
            logging.warning("Thiếu cấu hình Telegram, bỏ qua thông báo.")

        logging.info(f"Hoàn thành workflow trong {time.time() - start_time:.2f}s")
        return aligned_results

if __name__ == "__main__":
    proxies = {
        'http': 'http://rb-proxy-apac.bosch.com:8080',
        'https': 'http://rb-proxy-apac.bosch.com:8080'
    }
    manager = WorkflowManager(
        config_file='project_config.json',
        workflow_config_file='workflow_config.json',
        # proxies=proxies
    )
    manager.run()