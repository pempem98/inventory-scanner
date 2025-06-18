from django.db import models
import json

class Agent(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên đại lý")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Đại lý"
        verbose_name_plural = "Các Đại lý"

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
        verbose_name = "Cấu hình Dự án"
        verbose_name_plural = "Các Cấu hình Dự án"