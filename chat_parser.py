"""Parse AMP Minecraft console entries into simple events (no external dependencies)."""
import re

PLAYER = r'([A-Za-z0-9_]{3,16})'
CHAT_LINE = re.compile(r'(?:^|:\s*)(?:\[Not Secure\]\s*)?<' + PLAYER + r'>\s+(.+)$')
JOIN_LINE = re.compile(r'(?:^|:\s*)' + PLAYER + r' joined the game$')
LEAVE_LINE = re.compile(r'(?:^|:\s*)' + PLAYER + r' left the game$')
ADVANCEMENT_LINE = re.compile(r'(?:^|:\s*)' + PLAYER + r' (?:has made the advancement|has completed the challenge|has reached the goal) \[(.+)\]$')
DEATH_LINE = re.compile(
    r'(?:^|:\s*)' + PLAYER +
    r' (was slain by|was shot by|was killed by|fell from|fell off|fell out of|hit the ground|'
    r'drowned|burned to death|went up in flames|blew up|was blown up by|tried to swim in|'
    r'was pricked to death|was squashed by|suffocated in|starved to death|died|froze to death|'
    r'was struck by lightning|was impaled on|was pummeled by|walked into|was roasted in|'
    r'discovered the floor was lava|experienced kinetic energy|was obliterated by|was fireballed by)\b(.*)$',
    re.IGNORECASE,
)
CRASH_LINE = re.compile(r'Crash report saved to|Encountered an unexpected exception|Exception in server tick loop|This crash report has been saved', re.I)
VALID_PLAYER = re.compile('^' + PLAYER[1:-1] + '$')


def parse_entry(entry):
    """Return (kind, player, text): chat/join/leave/advancement/death/crash."""
    if not isinstance(entry, dict):
        return None
    content = str(entry.get('Contents') or '').strip()
    source = str(entry.get('Source') or '').strip()
    kind = str(entry.get('Type') or '').lower()
    if kind == 'chat' and VALID_PLAYER.fullmatch(source) and content:
        return ('chat', source, content)
    match = CHAT_LINE.search(content)
    if match:
        return ('chat', match.group(1), match.group(2))
    for kind_name, regex in (('join', JOIN_LINE), ('leave', LEAVE_LINE)):
        match = regex.search(content)
        if match:
            return (kind_name, match.group(1), '')
    match = ADVANCEMENT_LINE.search(content)
    if match:
        return ('advancement', match.group(1), match.group(2))
    match = DEATH_LINE.search(content)
    if match:
        return ('death', match.group(1), match.group(0).split(': ')[-1])
    if CRASH_LINE.search(content):
        return ('crash', '', content)
    return None
