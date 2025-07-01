import logging

class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        from .models import WorkerLog
        try:
            WorkerLog.objects.create(
                level=record.levelname,
                message=self.format(record)
            )
        except Exception:
            pass
