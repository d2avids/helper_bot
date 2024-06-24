import re
import os
from datetime import datetime, timedelta

TIMEZONE_OFFSET = int(os.getenv('TIMEZONE_OFFSET', 0))


def get_current_datetime():
    """Возвращает текущее время в выбранной таймзоне."""
    return datetime.now() + timedelta(hours=TIMEZONE_OFFSET)


def adjust_datetime_for_scheduler(dt: datetime) -> datetime:
    """Корректирует время в зависимости от TIMEZONE_OFFSET для передачи в планировщик."""
    return dt - timedelta(hours=TIMEZONE_OFFSET)


def validate_time_slot(time_slot):
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2} ([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$')
    match = pattern.match(time_slot)
    if match:
        date_part = time_slot.split()[0]
        start_time = match.group(1) + match.group(2)
        end_time = match.group(3) + match.group(4)
        try:
            datetime.strptime(date_part, '%Y-%m-%d')
            return start_time < end_time
        except ValueError:
            return False
    return False


def parse_time_slot(time_slot):
    date_part, times = time_slot.split()
    start_time_str, end_time_str = times.split('-')
    start_time = datetime.strptime(f"{date_part} {start_time_str}", '%Y-%m-%d %H:%M')
    end_time = datetime.strptime(f"{date_part} {end_time_str}", '%Y-%m-%d %H:%M')
    return start_time, end_time
