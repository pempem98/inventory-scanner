import json
from django.contrib import admin
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

# Import các model chính xác từ models.py
from .models import Agent, Project, ProjectConfig, Snapshot, InventoryChange
from .models import ColumnMapping, WorkerLog, ApartmentUnit

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    list_display_links = ('id', 'name')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'key_prefixes', 'telegram_chat_id')
    search_fields = ('name', 'telegram_chat_id')
    list_display_links = ('id', 'name')

class ColumnMappingInline(admin.TabularInline):
    model = ColumnMapping
    extra = 0
    fields = ('internal_name', 'display_name', 'aliases', 'is_identifier')
    verbose_name = "Cột tùy chỉnh"
    verbose_name_plural = "Các cột tùy chỉnh"

@admin.register(ProjectConfig)
class ProjectConfigAdmin(admin.ModelAdmin):
    list_display = ('id', '__str__', 'is_active', 'view_source_link')
    list_filter = ('project__name', 'agent__name', 'is_active')
    search_fields = ('project__name', 'agent__name')
    ordering = ('project__name', 'agent__name')
    list_display_links = ('id', '__str__')
    fieldsets = (
        ('Thông tin chung', {'fields': ('project', 'agent', 'is_active')}),
        ('Nguồn dữ liệu', {'fields': ('spreadsheet_id', 'gid', 'html_url')}),
        ('Cấu hình xử lý', {'fields': ('header_row_index', 'invalid_colors')}),
    )
    inlines = [ColumnMappingInline]

    @admin.display(description="Link nguồn")
    def view_source_link(self, obj):
        if obj.spreadsheet_id:
            url = f"https://docs.google.com/spreadsheets/d/{obj.spreadsheet_id}/edit#gid={obj.gid}"
            return format_html('<a href="{}" target="_blank">Mở Sheet</a>', url)
        if obj.html_url:
            return format_html('<a href="{}/#{}" target="_blank">Mở HTML</a>', obj.html_url, obj.gid)
        return "N/A"


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'project_data_source', 'timestamp')
    list_filter = ('project_data_source__project__name', 'project_data_source__agent__name', 'timestamp')
    search_fields = ('project_data_source__project__name', 'project_data_source__agent__name', 'data')
    readonly_fields = ('project_data_source', 'timestamp', 'display_pretty_data')
    fields = ('project_data_source', 'timestamp', 'display_pretty_data')
    ordering = ('-timestamp',)

    @admin.display(description="Quỹ căn hộ (dạng bảng)")
    def display_pretty_data(self, obj):
        try:
            data = json.loads(obj.data)
            if not isinstance(data, dict) or not data:
                return mark_safe(f"<pre><code>{escape(json.dumps(data, indent=2, ensure_ascii=False))}</code></pre>")
            first_item = next(iter(data.values()), {})
            headers = list(first_item.keys()) if isinstance(first_item, dict) else []
            html = '<table class="fixed-table"><thead><tr><th>Mã căn hộ</th>'
            for h in headers: html += f"<th>{escape(h)}</th>"
            html += '</tr></thead><tbody>'
            for key, row_data in data.items():
                html += f'<tr><td>{escape(key)}</td>'
                if isinstance(row_data, dict):
                    for h in headers: html += f'<td>{escape(row_data.get(h, ""))}</td>'
                else: html += f'<td colspan="{len(headers)}">{escape(row_data)}</td>'
                html += '</tr>'
            html += '</tbody></table>'
            return mark_safe(html)
        except Exception: return "Lỗi hiển thị dữ liệu."

    def has_add_permission(self, request):
        return False


@admin.register(WorkerLog)
class WorkerLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'level', 'message')
    list_filter = ('level', 'timestamp')
    search_fields = ('message',)
    readonly_fields = ('timestamp', 'level', 'message')

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(InventoryChange)
class InventoryChangeAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'project_config', 'change_type', 'apartment_key', 'details')
    list_filter = ('change_type', 'timestamp')
    search_fields = ('apartment_key',)
    readonly_fields = ('timestamp', 'project_config', 'change_type', 'apartment_key', 'details')
    ordering = ('-timestamp',)


@admin.register(ApartmentUnit)
class ApartmentUnitAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_project_data_source',
        'unit_code',
        'sales_policy',
        'get_source_url',
    )
    list_display_links = ('id', 'unit_code')
    search_fields = ('unit_code', 'project_config__project__name', 'project_config__agent__name')
    list_filter = ('project_config__project', 'project_config__agent')
    list_select_related = ('project_config', 'project_config__project')

    @admin.display(description="Nguồn dữ liệu dự án")
    def get_project_data_source(self, obj):
        """Lấy tên của ProjectConfig."""
        return str(obj.project_config)

    @admin.display(description="Link nguồn")
    def get_source_url(self, obj):
        """Hiển thị link nguồn dưới dạng một liên kết có thể nhấp."""
        config = obj.project_config
        if config and config.gid:
            if config.spreadsheet_id:
                url = f"https://docs.google.com/spreadsheets/d/{config.spreadsheet_id}/edit#gid={config.gid}"
                return format_html('<a href="{}" target="_blank">Mở Sheet</a>', url)
            if obj.html_url:
                return format_html('<a href="{}/#{}" target="_blank">Mở HTML</a>', config.html_url, config.gid)
        return "N/A"
