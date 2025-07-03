import csv
import json
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe

from .models import Agent, Project, ProjectConfig, Snapshot, InventoryChange
from .models import ColumnMapping, WorkerLog, ApartmentUnit, SystemConfig

def export_as_csv(modeladmin, request, queryset):
    """
    Hành động tùy chỉnh trong trang admin để xuất các đối tượng đã chọn ra file CSV.
    """
    opts = modeladmin.model._meta
    content_disposition = f'attachment; filename={opts.verbose_name_plural.replace(" ", "_")}.csv'
    fields = [field.name for field in opts.fields]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = content_disposition
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(fields)
    for obj in queryset:
        data_row = []
        for field in fields:
            value = getattr(obj, field)
            data_row.append(str(value))
        writer.writerow(data_row)        
    return response

export_as_csv.short_description = "Xuất các mục đã chọn"

@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('id', '__str__', 'telegram_bot_token', 'proxy_url')

    def has_add_permission(self, request):
        return SystemConfig.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    list_display_links = ('id', 'name')
    actions = [export_as_csv]
    list_per_page = 200
    list_max_show_all = 1000

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'key_prefixes', 'telegram_chat_id')
    search_fields = ('name', 'telegram_chat_id')
    list_display_links = ('id', 'name')
    actions = [export_as_csv]
    list_per_page = 200
    list_max_show_all = 1000

class ColumnMappingInline(admin.TabularInline):
    model = ColumnMapping
    extra = 0
    fields = ('internal_name', 'display_name', 'aliases', 'is_identifier')
    verbose_name = "Cột tùy chỉnh"
    verbose_name_plural = "Các cột tùy chỉnh"

@admin.register(ProjectConfig)
class ProjectConfigAdmin(admin.ModelAdmin):
    # Yêu cầu 1: Thêm spreadsheet_id, html_url, gid vào list_display
    list_display = ('id', '__str__', 'is_active', 'spreadsheet_id', 'html_url', 'gid', 'view_source_url')
    list_filter = ('project__name', 'agent__name', 'is_active')
    search_fields = ('project__name', 'agent__name', 'spreadsheet_id', 'html_url')
    ordering = ('project__name', 'agent__name')
    list_display_links = ('id', '__str__')
    readonly_fields = ('display_source_url',)

    fieldsets = (
        ('Thông tin chung', {'fields': ('project', 'agent', 'is_active')}),
        ('Nguồn dữ liệu', {
            'fields': ('display_source_url', 'spreadsheet_id', 'html_url', 'gid'),
            'description': 'Cấu hình nguồn dữ liệu để quét. Bạn có thể dùng Google Sheet (Spreadsheet ID và GID) hoặc một trang URL (HTML URL và GID).'
        }),
        ('Cấu hình xử lý', {'fields': ('header_row_index', 'invalid_colors')}),
    )
    inlines = [ColumnMappingInline]
    actions = [export_as_csv]
    list_per_page = 200
    list_max_show_all = 1000

    @admin.display(description="Source URL")
    def display_source_url(self, obj):
        """
        Tạo và hiển thị một liên kết URL có thể nhấp được.
        """
        link = "Vui lòng nhập nguồn cho link và lưu lại để xem."
        if obj.gid:
            if obj.spreadsheet_id and len(str(obj.spreadsheet_id)):
                url = f"https://docs.google.com/spreadsheets/d/{obj.spreadsheet_id}/edit#gid={obj.gid}"
                link = format_html('<a href="{}" target="_blank">{}</a>', url, url)
            elif obj.html_url and len(obj.html_url):
                anchor = f"#{str(obj.gid).strip('#')}" if f"{obj.gid}" else ""
                url = f"{str(obj.html_url).strip('/')}/{anchor}"
                link = format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return link

    @admin.display(description="Link nguồn")
    def view_source_url(self, obj):
        if obj.gid:
            if obj.spreadsheet_id:
                url = f"https://docs.google.com/spreadsheets/d/{obj.spreadsheet_id}/edit#gid={obj.gid}"
                return format_html('<a href="{}" target="_blank">Mở Sheet</a>', url)
            if obj.html_url:
                # GID trong trường hợp này có thể là ID của table hoặc anchor
                anchor = f"#{obj.gid}" if obj.gid else ""
                return format_html('<a href="{}{}" target="_blank">Mở HTML</a>', obj.html_url, anchor)
        return "N/A"

@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    # Yêu cầu 2: Thêm cột hiển thị các mã căn hộ
    list_display = ('id', 'project_data_source', 'timestamp', 'display_apartment_codes')
    list_filter = ('project_data_source__project__name', 'project_data_source__agent__name', 'timestamp')
    search_fields = ('project_data_source__project__name', 'project_data_source__agent__name', 'data')
    readonly_fields = ('project_data_source', 'timestamp', 'display_pretty_data')
    fields = ('project_data_source', 'timestamp', 'display_pretty_data')
    ordering = ('-timestamp',)
    actions = [export_as_csv]
    list_per_page = 200
    list_max_show_all = 1000

    @admin.display(description="Các mã căn hộ (một phần)")
    def display_apartment_codes(self, obj):
        """Hiển thị 5 mã căn hộ đầu tiên từ bản ghi."""
        try:
            data = json.loads(obj.data)
            # Lấy 5 'key' đầu tiên (là mã căn hộ)
            keys = list(data.keys())[:5]
            if not keys:
                return "(Không có dữ liệu)"

            # Nối các key lại và thêm '...' nếu có nhiều hơn 5
            display_text = ", ".join(keys)
            if len(data.keys()) > 5:
                display_text += ", ..."
            return display_text
        except (json.JSONDecodeError, AttributeError):
            return "Lỗi định dạng dữ liệu"

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
    actions = [export_as_csv]
    list_per_page = 200
    list_max_show_all = 1000

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
    actions = [export_as_csv]
    list_per_page = 200
    list_max_show_all = 1000

    @admin.display(description="Nguồn dữ liệu dự án")
    def get_project_data_source(self, obj):
        return str(obj.project_config)

    @admin.display(description="Link nguồn")
    def get_source_url(self, obj):
        config = obj.project_config
        if config and config.gid:
            if config.spreadsheet_id:
                url = f"https://docs.google.com/spreadsheets/d/{config.spreadsheet_id}/edit#gid={config.gid}"
                return format_html('<a href="{}" target="_blank">Mở Sheet</a>', url)
            if config.html_url:
                anchor = f"#{config.gid}" if config.gid else ""
                return format_html('<a href="{}{}" target="_blank">Mở HTML</a>', config.html_url, anchor)
        return "N/A"