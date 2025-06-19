# management/commands/run_tasks.py

import subprocess
from datetime import datetime
import logging

from django.core.management.base import BaseCommand
from django.conf import settings
from croniter import croniter
from management.models import ScheduledTask

# Cấu hình logging để ghi lại hoạt động
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Chạy các tác vụ định kỳ đã được cấu hình trong admin (sử dụng croniter).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Bắt đầu quét các tác vụ (dùng croniter) lúc {datetime.now()}..."))
        
        base_dir = settings.BASE_DIR
        active_tasks = ScheduledTask.objects.filter(is_active=True)
        now = datetime.now()

        for task in active_tasks:
            if not croniter.is_valid(task.cron_schedule):
                logger.error(f"Lịch chạy '{task.cron_schedule}' của tác vụ '{task.name}' không hợp lệ.")
                continue

            last_run = task.last_run_at or datetime(1970, 1, 1)
            
            iterator = croniter(task.cron_schedule, last_run)
            next_scheduled_run = iterator.get_next(datetime)

            if next_scheduled_run <= now:
                self.stdout.write(self.style.NOTICE(f"--> Đang chạy tác vụ: {task.name}"))
                try:
                    script_path = base_dir / task.task
                    subprocess.run(
                        ['/bin/bash', str(script_path)],
                        capture_output=True, text=True, check=True, encoding='utf-8'
                    )
                    self.stdout.write(self.style.SUCCESS(f"    Tác vụ '{task.name}' hoàn thành thành công."))
                except Exception as e:
                    logger.error(f"Lỗi khi chạy tác vụ '{task.name}': {e}")
                finally:
                    task.last_run_at = now
                    task.save()
        
        self.stdout.write(self.style.SUCCESS("Hoàn tất quét tác vụ."))