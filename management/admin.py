import json
from django.contrib import admin
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

from .models import Agent, ProjectConfig, Snapshot, ScheduledTask, ColumnMapping


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    list_display_links = ('id', 'name')


class ColumnMappingInline(admin.TabularInline):
    model = ColumnMapping
    extra = 0
    fields = ('internal_name', 'display_name', 'aliases', 'is_identifier')
    verbose_name = "Cột tùy chỉnh"
    verbose_name_plural = "Các cột tùy chỉnh"


@admin.register(ProjectConfig)
class ProjectConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent', 'project_name', 'spreadsheet_id', 'html_url', 'gid', 'is_active')
    list_filter = ('is_active', 'agent', 'project_name')
    search_fields = ('project_name', 'agent__name', 'spreadsheet_id', 'html_url', 'gid')
    ordering = ('agent', 'project_name')
    list_display_links = ('id',)
    fieldsets = (
        ('Thông tin chung', {'fields': ('agent', 'project_name', 'is_active')}),
        ('Nguồn dữ liệu', {'fields': ('spreadsheet_id', 'gid', 'html_url')}),
        ('Cấu hình xử lý', {
            'classes': (),
            'fields': ('header_row_index', 'key_prefixes', 'invalid_colors')
        }),
        ('Thông báo', {'fields': ('telegram_chat_id',)})
    )
    inlines = [ColumnMappingInline]


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    """Tùy chỉnh hiển thị cho Snapshot"""
    list_display = ('id', 'project_config', 'timestamp', 'display_inventory')
    list_filter = ('project_config', 'timestamp')
    search_fields = ('project_config__project_name', 'data')
    readonly_fields = ('project_config', 'timestamp', 'display_pretty_data')
    fields = ('project_config', 'timestamp', 'display_pretty_data')

    @admin.display(description="Hàng tồn (Mã căn hộ)")
    def display_inventory(self, obj):
        """
        Phương thức này đọc trường `data` (dạng JSON),
        trích xuất các mã căn hộ và hiển thị chúng.
        """
        try:
            inventory_data = json.loads(obj.data)
            if not isinstance(inventory_data, dict):
                return "Định dạng dữ liệu không hợp lệ"

            keys = list(inventory_data.keys())
            if not keys:
                return "---"

            keys = sorted(keys)
            display_text = ", ".join(keys)
            return format_html('<div style="max-width: 400px; word-wrap: break-word;">{}</div>', display_text)

        except json.JSONDecodeError:
            return "Lỗi định dạng JSON"
        except Exception:
            return "Lỗi không xác định"
        
    @admin.display(description="Quỹ căn hộ (dạng bảng)")
    def display_pretty_data(self, obj):
        """
        Định dạng chuỗi JSON thành một bảng HTML để dễ đọc.
        """
        try:
            data = json.loads(obj.data)
            if not isinstance(data, dict) or not data:
                pretty_json = json.dumps(data, indent=4, ensure_ascii=False)
                return mark_safe(f'<pre style="background-color: #1d1f21; color: #c5c8c6; padding: 15px; border-radius: 5px;"><code>{pretty_json}</code></pre>')

            nested_headers = list(next(iter(data.values())).keys())
            headers = ["Mã căn hộ"] + nested_headers
            
            table_style = "width:100%; border-collapse: collapse; border: 1px solid #ccc;"
            th_style = "border: 1px solid #ccc; padding: 8px; text-align: left; background-color: #f2f2f2; font-weight: bold;"
            td_style = "border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top;"
            
            html = f'<table style="{table_style}"><thead><tr>'
            for header in headers:
                html += f'<th style="{th_style}">{escape(header)}</th>'
            html += '</tr></thead>'
            
            html += '<tbody>'
            for key, row_data in data.items():
                html += '<tr>'
                for i, header in enumerate(headers):
                    value = key if i == 0 else row_data.get(header, "")
                    html += f'<td style="{td_style}">{escape(value)}</td>'
                html += '</tr>'
            html += '</tbody></table>'

            return mark_safe(html)

        except json.JSONDecodeError:
            return format_html('<div style="color: red;">Lỗi định dạng JSON.</div>')
        except Exception as e:
            return format_html('<div style="color: red;">Lỗi không xác định khi dựng bảng: {}</div>', str(e))

    def has_add_permission(self, request):
        return False
    

@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'task', 'cron_schedule', 'is_active', 'last_run_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'task')
    readonly_fields = ('last_run_at',)
