from django.db import models
import json

class Agent(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên đại lý")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Đại lý"
        verbose_name_plural = "Danh sách đại lý"

class ProjectConfig(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, verbose_name="Đại lý")
    project_name = models.CharField(max_length=100, verbose_name="Tên dự án")
    
    # Thông tin cấu hình
    spreadsheet_id = models.CharField(max_length=200, blank=True, null=True)
    gid = models.CharField(max_length=100)
    html_url = models.URLField(max_length=500, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")

    # Cấu hình tìm kiếm và xác thực
    header_row_index = models.PositiveIntegerField(blank=True, null=True, verbose_name="Dòng header (số)")
    key_column_aliases = models.JSONField(default=list, blank=True, verbose_name="Các tên cột Key")
    price_column_aliases = models.JSONField(default=list, blank=True, verbose_name="Các tên cột Giá")
    key_prefixes = models.JSONField(default=list, blank=True, verbose_name="Các tiền tố của Key")
    invalid_colors = models.JSONField(default=list, blank=True, verbose_name="Các màu không hợp lệ")

    def __str__(self):
        return f"{self.agent.name} - {self.project_name}"

    class Meta:
        verbose_name = "Đại lý & Dự án"
        verbose_name_plural = "Danh sách các dự án"

# --- BẮT ĐẦU MODEL MỚI ---
# Model này được tạo dựa trên schema SQL bạn cung cấp.
class Snapshot(models.Model):
    # Django tự động tạo trường 'id' tương ứng với 'id INTEGER PRIMARY KEY AUTOINCREMENT'

    # 'project_config_id' và FOREIGN KEY -> models.ForeignKey
    project_config = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, verbose_name="Đại lý & Dự án")

    # 'timestamp DATETIME DEFAULT CURRENT_TIMESTAMP' -> models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian tạo")

    # 'data TEXT NOT NULL' -> models.TextField
    data = models.TextField(verbose_name="Dữ liệu snapshot")

    def __str__(self):
        # Hiển thị một chuỗi đại diện hữu ích trong trang admin
        return f"Snapshot của '{self.project_config}' lúc {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "Bản ghi"
        verbose_name_plural = "Bản ghi quỹ căn hộ"
        # Sắp xếp các bản ghi theo thời gian, cái mới nhất sẽ ở trên cùng
        ordering = ['-timestamp']
# --- KẾT THÚC MODEL MỚI ---