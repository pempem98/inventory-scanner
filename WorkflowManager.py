import json
import os
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
from AgentConfig import AgentConfig
from GoogleSheetDownloader import GoogleSheetDownloader
from ExcelSnapshotComparator import ExcelSnapshotComparator

# Thiết lập logging với encoding UTF-8
logging.basicConfig(
    filename='workflow.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class WorkflowManager:
    """Quản lý workflow tải Google Sheet và so sánh snapshot."""
    
    def __init__(self, config_file: str, workflow_config_file: str = 'workflow_config.json', state_file: str = 'state.json', snapshot_dir: str = 'snapshots'):
        """
        Khởi tạo với file cấu hình, config workflow, file trạng thái và thư mục snapshot.
        
        Args:
            config_file: Đường dẫn đến file JSON chứa thông tin đại lý.
            workflow_config_file: Đường dẫn đến file JSON chứa config workflow.
            state_file: Đường dẫn đến file trạng thái.
            snapshot_dir: Thư mục lưu snapshot Excel.
        """
        self.config_file = config_file
        self.workflow_config_file = workflow_config_file
        self.state_file = state_file
        self.snapshot_dir = snapshot_dir
        self.state = self._load_state()
        self.configs = AgentConfig.load_from_json(config_file)
        self.workflow_config = self._load_workflow_config()
        
        # Tạo thư mục snapshots nếu chưa tồn tại
        if not os.path.exists(self.snapshot_dir):
            os.makedirs(self.snapshot_dir)
            logging.info(f"Đã tạo thư mục {self.snapshot_dir}.")
    
    def _load_state(self) -> Dict[str, Any]:
        """Đọc file trạng thái."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logging.error(f"Lỗi khi đọc file trạng thái {self.state_file}: {e}")
            return {}
    
    def _save_state(self) -> None:
        """Lưu trạng thái vào file."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logging.error(f"Lỗi khi lưu file trạng thái {self.state_file}: {e}")
    
    def _load_workflow_config(self) -> Dict[str, Any]:
        """Đọc file config workflow."""
        default_config = {'allowed_key_pattern': r'^[A-Za-z0-9_]+$'}
        try:
            if os.path.exists(self.workflow_config_file):
                with open(self.workflow_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    raise ValueError("File workflow config phải là dictionary.")
                return config
            logging.warning(f"File {self.workflow_config_file} không tồn tại, dùng config mặc định.")
            return default_config
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {self.workflow_config_file}: {e}, dùng config mặc định.")
            return default_config
    
    def _get_file_name(self, agent_name: str, config: AgentConfig.Config, date: str) -> str:
        """Tạo tên file theo định dạng snapshots/YYMMDD_{agent_name}_{project_name}.xlsx."""
        clean_project_name = config.project_name.replace(' ', '_')
        file_name = f"{date}_{agent_name}_{clean_project_name}.xlsx"
        return os.path.join(self.snapshot_dir, file_name)
    
    def _download_snapshot(self, agent_name: str, config: AgentConfig.Config, date: str) -> str:
        """Tải Google Sheet và lưu snapshot."""
        file_name = self._get_file_name(agent_name, config, date)
        
        # Tạo khóa trạng thái dựa trên agent_name và project_name
        agent_state = self.state.get(agent_name, {}).get(config.project_name, {})
        if agent_state.get(f'download_{date}') == 'completed' and os.path.exists(file_name):
            logging.info(f"Bỏ qua tải snapshot {file_name} cho {agent_name}/{config.project_name}: đã hoàn thành.")
            return file_name
        
        try:
            downloader = GoogleSheetDownloader(config.spreadsheet_id, config.gid)
            downloader.download(output_file=file_name)
            
            agent_state[f'download_{date}'] = 'completed'
            self.state.setdefault(agent_name, {}).setdefault(config.project_name, {}).update(agent_state)
            self._save_state()
            logging.info(f"Tải thành công snapshot {file_name} cho {agent_name}/{config.project_name}.")
            return file_name
        except Exception as e:
            logging.error(f"Lỗi khi tải snapshot {file_name} cho {agent_name}/{config.project_name}: {e}")
            return ''
    
    def _compare_snapshots(self, agent_name: str, config: AgentConfig.Config, predecessor_file: str, current_file: str) -> None:
        """So sánh hai snapshot."""
        agent_state = self.state.get(agent_name, {}).get(config.project_name, {})
        compare_key = f"compare_{os.path.basename(predecessor_file)}_{os.path.basename(current_file)}"
        if agent_state.get(compare_key) == 'completed':
            logging.info(f"Bỏ qua so sánh {predecessor_file} và {current_file} cho {agent_name}/{config.project_name}: đã hoàn thành.")
            return
        
        try:
            if not os.path.exists(predecessor_file) or not os.path.exists(current_file):
                raise FileNotFoundError(f"Thiếu file: {predecessor_file} hoặc {current_file}")
            
            comparator = ExcelSnapshotComparator(
                file_predecessor=predecessor_file,
                file_current=current_file,
                key_col=config.key_column,
                check_cols=config.check_columns,
                allowed_key_pattern=self.workflow_config.get('allowed_key_pattern')
            )
            comparator.compare()
            
            agent_state[compare_key] = 'completed'
            self.state.setdefault(agent_name, {}).setdefault(config.project_name, {}).update(agent_state)
            self._save_state()
            logging.info(f"So sánh thành công {predecessor_file} và {current_file} cho {agent_name}/{config.project_name}.")
        except Exception as e:
            logging.error(f"Lỗi khi so sánh {predecessor_file} và {current_file} cho {agent_name}/{config.project_name}: {e}")
    
    def run(self) -> None:
        """Chạy toàn bộ workflow."""
        current_date = datetime.now().strftime('%y%m%d')
        predecessor_date = (datetime.now() - timedelta(days=1)).strftime('%y%m%d')
        
        for agent_config in self.configs:
            logging.info(f"Bắt đầu xử lý đại lý {agent_config.agent_name}...")
            
            for config in agent_config.configs:
                try:
                    # Tải snapshot hiện tại
                    current_file = self._download_snapshot(agent_config.agent_name, config, current_date)
                    if not current_file:
                        logging.warning(f"Bỏ qua so sánh cho {agent_config.agent_name}/{config.project_name}: không có snapshot current.")
                        continue

                    # Giả định file predecessor đã có sẵn
                    predecessor_file = self._get_file_name(agent_config.agent_name, config, predecessor_date)
                    if not os.path.exists(predecessor_file):
                        logging.warning(f"Bỏ qua so sánh cho {agent_config.agent_name}/{config.project_name}: không tìm thấy snapshot predecessor {predecessor_file}.")
                        continue
                    
                    
                    self._compare_snapshots(agent_config.agent_name, config, predecessor_file, current_file)
                    
                except Exception as e:
                    logging.error(f"Lỗi tổng quát khi xử lý {agent_config.agent_name}/{config.project_name}: {e}")
                    continue
    
    def reset_state(self) -> None:
        """Xóa trạng thái cho snapshot current và trạng thái so sánh."""
        current_date = datetime.now().strftime('%y%m%d')
        new_state = {}
        
        for agent_name, agent_data in self.state.items():
            new_agent_data = {}
            for project_name, agent_state in agent_data.items():
                new_agent_state = {}
                for key, value in agent_state.items():
                    # Bỏ qua các khóa download_{current_date} và compare_
                    if key != f'download_{current_date}' and not key.startswith('compare_'):
                        new_agent_state[key] = value
                if new_agent_state:
                    new_agent_data[project_name] = new_agent_state
            if new_agent_data:
                new_state[agent_name] = new_agent_data
        
        self.state = new_state
        self._save_state()
        logging.info("Đã reset trạng thái cho snapshot current và trạng thái so sánh.")

# Chạy ví dụ
if __name__ == "__main__":
    need_reset = input("Bạn có muốn reset trạng thái không? (y/n): ").strip().lower()
    try:
        manager = WorkflowManager(config_file='project_config.json')
        if need_reset == 'y':
            manager.reset_state()
        manager.run()
    except Exception as e:
        logging.error(f"Lỗi workflow: {e}")