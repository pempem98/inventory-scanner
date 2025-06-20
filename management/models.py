from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
import json


def get_default_invalid_colors():
    """Trả về danh sách các màu không hợp lệ mặc định."""
    return ["#ff0000", "#ea4335"]

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
    key_prefixes = models.JSONField(default=list, verbose_name="Các tiền tố của mã căn hộ")
    invalid_colors = models.JSONField(default=get_default_invalid_colors, blank=True, verbose_name="Các màu không hợp lệ")

    def __str__(self):
        return f"{self.agent.name} - {self.project_name}"

    def clean(self):
        super().clean()
        if not self.spreadsheet_id and not self.html_url:
            raise ValidationError(
                "Bạn phải điền ít nhất một trong hai trường 'Spreadsheet ID' hoặc 'HTML URL'."
            )

    class Meta:
        verbose_name = "Đại lý & Dự án"
        verbose_name_plural = "Danh sách các dự án"

class Snapshot(models.Model):
    project_config = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, verbose_name="Đại lý & Dự án")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian tạo")
    data = models.TextField(verbose_name="Bản ghi quỹ căn hộ")

    def __str__(self):
        return f"Snapshot của '{self.project_config}' lúc {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "Bản ghi quỹ căn hộ"
        verbose_name_plural = "Danh sách bản ghi quỹ căn hộ"
        ordering = ['-timestamp']

class ColumnMapping(models.Model):
    project_config = models.ForeignKey(ProjectConfig, on_delete=models.CASCADE, related_name="column_mappings", verbose_name="Cấu hình Dự án")
    internal_name = models.CharField(max_length=50, verbose_name="Tên", help_text="Tên dùng trong code, ví dụ: 'key', 'price', 'policy'. Viết liền, không dấu.")
    display_name = models.CharField(max_length=100, verbose_name="Mô tả", help_text="Tên sẽ hiển thị trong các thông báo.")
    aliases = models.JSONField(default=list, verbose_name="Các tên tiêu đề có thể có", help_text="Danh sách các tên tiêu đề trong file nguồn, dạng JSON list.")
    is_identifier = models.BooleanField(default=False, verbose_name="Là cột định danh?", help_text="Tích vào đây nếu đây là cột chứa mã định danh duy nhất (ví dụ: Mã căn hộ).")

    def __str__(self):
        return f"{self.display_name} (cho {self.project_config.project_name})"

    class Meta:
        verbose_name = "Ánh xạ Tiêu đề"
        verbose_name_plural = "Các ánh xạ Tiêu đề"
        unique_together = ('project_config', 'internal_name')

@receiver(post_save, sender=ProjectConfig)
def create_default_column_mapping(sender, instance, created, **kwargs):
    if created:
        ColumnMapping.objects.get_or_create(
            project_config=instance,
            internal_name='key',
            defaults={
                "display_name": "Mã căn hộ",
                "aliases": [
                    "Mã",
                    "Mã căn",
                    "Mã căn hộ",
                ],
                "is_identifier": True
            }
        )
        ColumnMapping.objects.get_or_create(
            project_config=instance,
            internal_name='price',
            defaults={
                "display_name": "Giá TTS",
                "aliases": [
                    'Giá TTS',
                    'Giá TTS',
                    'Giá thanh toán sớm',
                    'Giá TTS tạm tính',
                    'Gía TTS (tạm tinh)',
                    'Giá TTS (tạm tính)',
                    'Giá TTS sau CK',
                    'Giá TTS (gồm VAT+KPBT)',
                    'Giá TTS (tạm tính) (đã gồm VAT+KPBT)'
                    'TTS',
                    'TTS(*)',
                    'TTS tạm tính',
                    'TTS (tạm tính)',
                    'TTS (tạm tính)(đã bao gồm VAT+KPBT)',
                ],
                "is_identifier": False
            }
        )
        ColumnMapping.objects.get_or_create(
            project_config=instance,
            internal_name='policy',
            defaults={
                "display_name": "CSBH",
                "aliases": [
                    'CSBH',
                    'CSBH Ngày',
                    'Chính sách',
                ],
                "is_identifier": False
            }
        )
