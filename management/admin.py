from django.contrib import admin
from .models import Agent, ProjectConfig

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
        (
            'Thông tin chung',
            {
                'fields': ('agent', 'project_name', 'is_active')
            }
        ),
        (
            'Nguồn dữ liệu',
            {
                'fields': ('spreadsheet_id', 'gid', 'html_url')
            }
        ),
        (
            'Cấu hình xử lý',
            {
                'classes': ('collapse',),
                'fields': (
                    'header_row_index',
                    'key_column_aliases',
                    'price_column_aliases',
                    'key_prefixes',
                    'invalid_colors'
                )
            }
        ),
        (
            'Thông báo',
            {
                'fields': ('telegram_chat_id',)
            }
        )
    )
