import subprocess
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Chạy script entry_point.sh để thực thi workflow chính.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Bắt đầu thực thi entry_point.sh...")

        # Giả sử entry_point.sh nằm ở thư mục gốc của project
        script_path = './entry_point.sh'

        try:
            # Gọi script bash và chờ nó hoàn thành
            result = subprocess.run(
                [script_path], 
                check=True, 
                capture_output=True, 
                text=True,
                shell=True # Dùng shell=True để các lệnh như `source` hoạt động
            )
            self.stdout.write(self.style.SUCCESS('entry_point.sh đã chạy thành công!'))
            self.stdout.write('--- Output ---')
            self.stdout.write(result.stdout)
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR('Có lỗi xảy ra khi chạy entry_point.sh.'))
            self.stderr.write('--- Error ---')
            self.stderr.write(e.stderr)