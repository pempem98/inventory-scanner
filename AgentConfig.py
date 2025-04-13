import json
from typing import List, Dict, Any
import re

class AgentConfig:
    """Class lưu trữ danh sách cấu hình của một đại lý từ file JSON."""

    class Config:
        """Lớp nội bộ để lưu trữ một cấu hình đơn lẻ."""
        def __init__(
            self,
            project_name: str,
            spreadsheet_id: str,
            gid: str,
            key_column: str,
            check_columns: List[str]
        ):
            self.project_name = project_name
            self.spreadsheet_id = spreadsheet_id
            self.gid = gid
            self.key_column = key_column
            self.check_columns = check_columns

            # Kiểm tra dữ liệu
            self._validate()

        def _validate(self) -> None:
            """Kiểm tra dữ liệu hợp lệ."""
            if not self.project_name or not isinstance(self.project_name, str):
                raise ValueError("Tên dự án phải là chuỗi không rỗng.")
            if not self.spreadsheet_id or not isinstance(self.spreadsheet_id, str):
                raise ValueError("Spreadsheet ID phải là chuỗi không rỗng.")
            if not self.gid or not isinstance(self.gid, str):
                raise ValueError("GID phải là chuỗi không rỗng.")
            if not self._is_valid_excel_col(self.key_column):
                raise ValueError(f"Ký hiệu cột key '{self.key_column}' không hợp lệ.")
            if not self.check_columns or not all(self._is_valid_excel_col(col) for col in self.check_columns):
                raise ValueError(f"Danh sách cột kiểm tra {self.check_columns} chứa ký hiệu không hợp lệ.")

        @staticmethod
        def _is_valid_excel_col(col: str) -> bool:
            """Kiểm tra ký hiệu cột Excel hợp lệ (A-Z, AA-ZZ, ...)."""
            return bool(col and isinstance(col, str) and re.match(r'^[A-Z]+$', col.upper()))

        def __repr__(self) -> str:
            """Biểu diễn chuỗi của cấu hình."""
            return (f"Config(project_name='{self.project_name}', "
                    f"spreadsheet_id='{self.spreadsheet_id}', gid='{self.gid}', "
                    f"key_column='{self.key_column}', check_columns={self.check_columns})")

    def __init__(self, agent_name: str, configs: List['AgentConfig.Config']):
        """
        Khởi tạo với tên đại lý và danh sách cấu hình.

        Args:
            agent_name: Tên đại lý.
            configs: Danh sách các cấu hình.

        Raises:
            ValueError nếu dữ liệu không hợp lệ.
        """
        self.agent_name = agent_name
        self.configs = configs

        # Kiểm tra tên đại lý
        if not self.agent_name or not isinstance(self.agent_name, str):
            raise ValueError("Tên đại lý phải là chuỗi không rỗng.")
        if not self.configs:
            raise ValueError("Danh sách cấu hình không được rỗng.")

    @classmethod
    def from_dict(cls, agent_name: str, data: Any) -> 'AgentConfig':
        """
        Tạo AgentConfig từ dictionary hoặc danh sách dictionary.

        Args:
            agent_name: Tên đại lý.
            data: Dictionary hoặc danh sách dictionary chứa thông tin cấu hình.

        Returns:
            Instance của AgentConfig.
        """
        configs = []
        # Hỗ trợ JSON cũ (một dictionary)
        if isinstance(data, dict):
            configs.append(cls.Config(
                project_name=data['project_name'],
                spreadsheet_id=data['spreadsheet_id'],
                gid=data['gid'],
                key_column=data['key_column'],
                check_columns=data['check_columns']
            ))
        # Hỗ trợ JSON mới (danh sách dictionary)
        elif isinstance(data, list):
            for item in data:
                configs.append(cls.Config(
                    project_name=item['project_name'],
                    spreadsheet_id=item['spreadsheet_id'],
                    gid=item['gid'],
                    key_column=item['key_column'],
                    check_columns=item['check_columns']
                ))
        else:
            raise ValueError(f"Dữ liệu cấu hình cho {agent_name} không hợp lệ: phải là dictionary hoặc danh sách dictionary.")

        return cls(agent_name, configs)

    @classmethod
    def load_from_json(cls, json_file: str) -> List['AgentConfig']:
        """
        Load danh sách AgentConfig từ file JSON.

        Args:
            json_file: Đường dẫn đến file JSON.

        Returns:
            Danh sách các instance AgentConfig.

        Raises:
            FileNotFoundError nếu file không tồn tại.
            ValueError nếu JSON không hợp lệ.
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("File JSON phải là một dictionary.")

            configs = []
            for agent_name, config_data in data.items():
                config = cls.from_dict(agent_name, config_data)
                configs.append(config)

            return configs
        except FileNotFoundError:
            raise FileNotFoundError(f"File JSON {json_file} không tồn tại.")
        except json.JSONDecodeError:
            raise ValueError(f"File JSON {json_file} không hợp lệ.")
        except KeyError as e:
            raise ValueError(f"File JSON thiếu trường bắt buộc: {e}")

    def __repr__(self) -> str:
        """Biểu diễn chuỗi của đối tượng."""
        configs_str = ', '.join(str(config) for config in self.configs)
        return f"AgentConfig(agent_name='{self.agent_name}', configs=[{configs_str}])"

# Chạy ví dụ
if __name__ == "__main__":
    # Load từ file JSON
    try:
        configs = AgentConfig.load_from_json('project_config.json')
        for config in configs:
            print(config)
    except Exception as e:
        print(f"Lỗi: {e}")