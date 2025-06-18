from django.contrib import admin
from .models import Agent, ProjectConfig, Snapshot
import json
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    list_display_links = ('id', 'name')


@admin.register(ProjectConfig)
class ProjectConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent', 'project_name', 'spreadsheet_id', 'html_url', 'gid', 'is_active')
    list_filter = ('is_active', 'agent', 'project_name')
    search_fields = ('project_name', 'agent__name', 'spreadsheet_id', 'html_url', 'gid')
    ordering = ('agent', 'project_name')
    list_display_links = ('id', 'project_name')
    fieldsets = (
        ('Thông tin chung', {'fields': ('agent', 'project_name', 'is_active')}),
        ('Nguồn dữ liệu', {'fields': ('spreadsheet_id', 'gid', 'html_url')}),
        ('Cấu hình xử lý', {'classes': ('collapse',), 'fields': ('header_row_index', 'key_column_aliases', 'price_column_aliases', 'key_prefixes', 'invalid_colors')}),
        ('Thông báo', {'fields': ('telegram_chat_id',)})
    )


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    """Tùy chỉnh hiển thị cho Snapshot"""
    # 2. Thêm cột 'Hàng tồn' vào danh sách hiển thị
    list_display = ('id', 'project_config', 'timestamp', 'display_inventory')
    list_filter = ('project_config', 'timestamp')
    
    # 3. Cho phép tìm kiếm cả trong trường 'data'
    search_fields = ('project_config__project_name', 'data')
    
    readonly_fields = ('project_config', 'timestamp', 'display_pretty_data')
    fields = ('project_config', 'timestamp', 'display_pretty_data')

    # 4. Định nghĩa phương thức để tạo cột "Hàng tồn"
    @admin.display(description="Hàng tồn (Mã căn hộ)")
    def display_inventory(self, obj):
        """
        Phương thức này đọc trường `data` (dạng JSON),
        trích xuất các mã căn hộ và hiển thị chúng.
        """
        try:
            # Tải dữ liệu JSON từ trường data
            inventory_data = json.loads(obj.data)
            
            # Giả định dữ liệu là một danh sách các dictionary, ví dụ: [{"key": "A101"}, ...]
            if not isinstance(inventory_data, dict):
                return "Định dạng dữ liệu không hợp lệ"

            # Trích xuất tất cả các giá trị của 'key'
            keys = list(inventory_data.keys())
            
            if not keys:
                return "---"

            # Định dạng hiển thị để giao diện không bị vỡ nếu có quá nhiều mã
            keys = sorted(keys)
            display_text = ", ".join(keys)
            
            # Sử dụng format_html để đảm bảo an toàn và hiển thị đúng
            return format_html('<div style="max-width: 400px; word-wrap: break-word;">{}</div>', display_text)

        except json.JSONDecodeError:
            return "Lỗi định dạng JSON"
        except Exception:
            return "Lỗi không xác định"
        
    @admin.display(description="Dữ liệu Snapshot (dạng bảng)")
    def display_pretty_data(self, obj):
        """
        Định dạng chuỗi JSON thành một bảng HTML để dễ đọc.
        """
        try:
            data = json.loads(obj.data)

            # Chỉ xử lý nếu dữ liệu là một danh sách và không rỗng
            if not isinstance(data, dict) or not data:
                # Nếu không, quay về hiển thị dạng text đã định dạng
                pretty_json = json.dumps(data, indent=4, ensure_ascii=False)
                return mark_safe(f'<pre style="background-color: #1d1f21; color: #c5c8c6; padding: 15px; border-radius: 5px;"><code>{pretty_json}</code></pre>')

            nested_headers = list(next(iter(data.values())).keys())
            headers = ["Mã căn hộ"] + nested_headers
            
            # Bắt đầu xây dựng bảng HTML
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
                    # Lấy giá trị, escape để đảm bảo an toàn, và để trống nếu không có
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