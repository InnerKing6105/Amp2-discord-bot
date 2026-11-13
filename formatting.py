"""AMP-to-Discord display helpers, independent of Discord and credentials."""

import re

STATE_NAMES = {
    -1: 'Undefined', 0: 'Stopped', 5: 'Pre-start', 7: 'Configuring',
    10: 'Starting', 20: 'Online', 30: 'Restarting', 40: 'Stopping',
    45: 'Preparing to sleep', 50: 'Sleeping', 60: 'Waiting',
    70: 'Installing', 75: 'Updating', 80: 'Awaiting input',
    100: 'Failed', 200: 'Suspended', 250: 'Maintenance', 999: 'Unknown',
}
PLAYER = re.compile(r'^[A-Za-z0-9_]{3,16}$')
CONTROL = re.compile(r'[\x00-\x1f\x7f]')


def state_code(status):
    if not isinstance(status, dict):
        return None
    try:
        return int(status.get('State'))
    except (TypeError, ValueError):
        return None


def pretty_state(status):
    code = state_code(status)
    if code is None:
        return 'Unknown'
    return STATE_NAMES.get(code, f'State {code}')


def safe_text(value, limit=200):
    """Neutralize Discord mentions and invisible control chars in Minecraft/AMP output."""
    text = CONTROL.sub(' ', str(value or '')).strip()
    text = text.replace('@', '@\u200b').replace('`', "'")
    return text[:limit]


def format_uptime(value):
    if value is None or value == '':
        return 'Not available'
    if isinstance(value, (int, float)):
        seconds = max(0, int(value))
        days, remaining = divmod(seconds, 86400)
        hours, remaining = divmod(remaining, 3600)
        mins, _ = divmod(remaining, 60)
        return f'{days}d {hours}h {mins}m' if days else f'{hours}h {mins}m'
    return safe_text(value, 50)


def _metrics(status):
    return status.get('Metrics') or {} if isinstance(status, dict) else {}


def find_metric(status, *names):
    """Return AMP metric and its label; no invented values when unavailable."""
    metrics = _metrics(status)
    if not isinstance(metrics, dict):
        return None, ''
    for term in names:
        for label, metric in metrics.items():
            if term in str(label).lower() and isinstance(metric, dict):
                return metric, str(label)
    return None, ''


def metric_display(status, *names):
    metric, label = find_metric(status, *names)
    if metric is None:
        return 'Not available'
    raw = metric.get('RawValue')
    units = str(metric.get('Units') or '')
    if raw is not None:
        rawtext = f'{raw:.1f}' if isinstance(raw, float) else str(raw)
        return safe_text(f'{rawtext} {units}', 60)
    pct = metric.get('Percent')
    if pct is not None:
        return f'{pct}%'
    return 'Not available'


def metric_percent(status, *names):
    metric, _ = find_metric(status, *names)
    if not metric:
        return None
    try:
        value = metric.get('Percent')
        if value is None and str(metric.get('Units', '')).strip() == '%':
            value = metric.get('RawValue')
        result = float(value)
        return result if 0 <= result <= 100 else None
    except (TypeError, ValueError):
        return None


def players_from_api(result):
    """AMP Core/GetUserList generally maps player UUID to player metadata."""
    if isinstance(result, dict):
        if 'Result' in result and isinstance(result['Result'], (dict, list)):
            return players_from_api(result['Result'])
        items = list(result.values())
    elif isinstance(result, list):
        items = result
    else:
        return []
    players = set()
    for item in items:
        if isinstance(item, str) and PLAYER.fullmatch(item):
            players.add(item)
        elif isinstance(item, dict):
            name = item.get('Name') or item.get('name') or item.get('Username') or item.get('username')
            if isinstance(name, str) and PLAYER.fullmatch(name):
                players.add(name)
    return sorted(players, key=str.lower)


def player_count(status, players=None):
    """Use AMP live count where present; empty player list is not always authoritative."""
    if not isinstance(status, dict):
        return ('Not available', 'Not available')
    for key in ('ActiveUsers', 'CurrentPlayers', 'PlayerCount'):
        count = status.get(key)
        if isinstance(count, (int, float)):
            max_users = status.get('MaxUsers') or status.get('MaxPlayers')
            return (str(int(count)), str(int(max_users)) if isinstance(max_users, (int, float)) else '—')
    return (str(len(players)), '—') if players is not None else ('Not available', '—')
