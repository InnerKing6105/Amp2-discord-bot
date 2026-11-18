"""Pure helpers for AMP backup inventory, spark's console report, and timed restarts.

Does not manage credentials or mutate a Minecraft world.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re

ANSI = re.compile(r'\x1b\[[0-9;]*m')
MC_COLOR = re.compile(r'§[0-9a-fk-or]', re.I)
NUMBER = re.compile(r'\*?([0-9]+(?:\.[0-9]+)?)')
BACKUP_DATE_KEYS = ('Timestamp', 'timestamp', 'Created', 'created', 'CreationTime', 'CreatedAt', 'created_at')
FLOATS = r'\*?(\d+(?:\.\d+)?)'


def text_from_entry(entry):
    if not isinstance(entry, dict):
        return ''
    if str(entry.get('Type', '')).lower() == 'chat':
        return ''
    return MC_COLOR.sub('', ANSI.sub('', str(entry.get('Contents') or ''))).strip()


def parse_time(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    elif isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    else:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def backup_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ('Backups', 'backups', 'Result', 'result'):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError('AMP backup API returned an unexpected shape')


def last_backup(payload):
    """Return newest verified inventory item or None; don't imply a schedule succeeded."""
    entries = backup_list(payload)
    matches = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        timestamp = next((parse_time(item.get(k)) for k in BACKUP_DATE_KEYS if parse_time(item.get(k))), None)
        if timestamp:
            matches.append((timestamp, item))
    return max(matches, key=lambda p: p[0]) if matches else None


def backup_age_hours(item, now=None):
    now = now or datetime.now(timezone.utc)
    if not item:
        return None
    return max(0.0, (now - item[0]).total_seconds() / 3600)


class SparkSampler:
    """Read two labelled lines of `spark tps` output; never treat guessed metrics as measured."""

    def __init__(self):
        self.request_at = None
        self.tps = None
        self.mspt_median = None
        self.mspt_p95 = None
        self.measured_at = None
        self.last_mspt_at = None
        self._waiting_for = None

    def start(self, now):
        self.request_at = now
        self._waiting_for = None

    def consume(self, entry, now):
        if self.request_at is None or (now - self.request_at).total_seconds() > 40:
            return False
        line = text_from_entry(entry)
        if not line:
            return False
        line = re.sub(r'^.*?(?:\]:\s*|\]\s*:\s*)', '', line, count=1).strip()
        # Spark includes a lightning glyph and other formatting before reports.
        low = line.lower()
        if 'tps from last' in low:
            self._waiting_for = 'tps'
            return True
        if 'tick durations' in low and 'ms' in low:
            self._waiting_for = 'mspt'
            return True
        if self._waiting_for == 'tps':
            nums = NUMBER.findall(line)
            # Must have at least the 5s, 10s, 1m windows.
            if len(nums) >= 3 and len(nums) <= 6:
                value = float(nums[2]); self._waiting_for = None
                if 0 <= value <= 100:
                    self.tps = value
                    self.measured_at = now
                    return True
            self._waiting_for = None
        if self._waiting_for == 'mspt':
            # Spark min/median/p95/max per window; first 10s window before semicolon.
            report = line.split(';')[0]
            nums = NUMBER.findall(report)
            if len(nums) == 4:
                median, p95 = float(nums[1]), float(nums[2])
                self._waiting_for = None
                if 0 <= median <= p95 <= 1_000_000:
                    self.mspt_median, self.mspt_p95 = median, p95
                    self.measured_at = now
                    self.last_mspt_at = now
                    return True
            self._waiting_for = None
        return False

    def display(self, now, max_age_seconds=600):
        if self.measured_at is None or (now - self.measured_at).total_seconds() > max_age_seconds:
            return 'Not available', 'Not available'
        tps = f'{self.tps:.2f} TPS (1m)' if self.tps is not None else 'Not available'
        mspt = (f'{self.mspt_median:.1f} median / {self.mspt_p95:.1f} p95 ms (10s)'
                if self.mspt_median is not None else 'Not available')
        return tps, mspt


def parse_restart_clock(value):
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('RESTART_AT must be in HH:MM 24-hour format')
    return tuple(int(part) for part in value.split(':'))


def restart_actions(now, clock, warned, completed, warn_minutes=(15, 5, 1)):
    """Return actions due for today in local time. Skip late invocations (>120s)."""
    if now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    target = now.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0)
    today = now.date().isoformat()
    if completed == today:
        return []
    remaining = (target - now).total_seconds()
    actions = []
    if 0 <= remaining <= max(warn_minutes) * 60:
        for minute in sorted(set(warn_minutes), reverse=True):
            # A warning needs to fall within its own 30-second delivery window.
            if minute not in warned and minute * 60 - 30 < remaining <= minute * 60:
                actions.append(('warn', minute))
    if -120 <= remaining <= 0:
        actions.append(('restart', 0))
    return actions


def local_now(tz_name):
    return datetime.now(ZoneInfo(tz_name))
