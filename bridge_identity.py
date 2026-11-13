"""Player avatar URLs and safe Minecraft-facing Discord usernames.

No network calls and no Discord dependency: easy to test without AMP credentials.
"""

import json
from pathlib import Path
import re
import unicodedata

# Minecraft Java profile names are case-insensitive, ASCII, and 3-16 characters.
MC_PLAYER = re.compile(r"[A-Za-z0-9_]{3,16}\Z")
MC_UUID = re.compile(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\Z")
MC_TEXTURE = re.compile(r"[0-9a-fA-F]{64}\Z")


def load_avatar_overrides(file_path):
    """Map lowercase player names to verified MC usernames, UUIDs or texture IDs.

    Avoid accepting arbitrary URLs: Discord webhooks fetch external images.
    """
    path = Path(file_path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid data/player_avatars.json; expected a JSON object") from exc
    if not isinstance(raw, dict):
        raise ValueError("data/player_avatars.json must contain a JSON object")
    result = {}
    for name, identifier in raw.items():
        if not isinstance(name, str) or not MC_PLAYER.fullmatch(name):
            raise ValueError("Avatar override keys must be valid Minecraft usernames")
        if not isinstance(identifier, str) or not valid_avatar_identifier(identifier):
            raise ValueError(f"Invalid avatar identifier for Minecraft player {name!r}")
        result[name.casefold()] = identifier
    return result


def valid_avatar_identifier(identifier):
    return bool(isinstance(identifier, str) and (
        MC_PLAYER.fullmatch(identifier) or MC_UUID.fullmatch(identifier) or MC_TEXTURE.fullmatch(identifier)
    ))


def avatar_url(player, overrides=None, size=96):
    """Use MCHeads, which supports username, account UUID and skin texture ID.

    Unknown/offline-mode names may render the default skin. Provide an override
    with the player's real Java UUID or texture ID to show the desired skin.
    """
    if not isinstance(player, str) or not MC_PLAYER.fullmatch(player):
        return None
    identifier = (overrides or {}).get(player.casefold(), player)
    if not valid_avatar_identifier(identifier):
        return None
    pixels = max(16, min(int(size), 256))
    return f"https://mc-heads.net/avatar/{identifier}/{pixels}.png"


def _clean_mc_name(value):
    """Keep readable Unicode but strip control, formatting, and bidi spoofing."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    result = []
    for char in value:
        category = unicodedata.category(char)
        if char == '§' or category.startswith('C') or category in {'Zl', 'Zp'}:
            continue
        result.append(char)
    return ' '.join(''.join(result).split())[:32]


def discord_minecraft_name(user, source="username"):
    """Use the Discord account username by default, not a decorative nickname.

    discord.py Member.display_name can contain fancy Unicode that the previous
    ASCII-only regex dropped entirely, producing 'Discord user' in Minecraft.
    """
    account_username = getattr(user, "name", "")
    display_name = getattr(user, "display_name", "")
    choices = ((display_name, account_username) if source == "display" else
               (account_username, display_name))
    for candidate in choices:
        cleaned = _clean_mc_name(candidate)
        if cleaned and any(ch.isalnum() for ch in cleaned):
            return cleaned
    # Last-resort identifier (never send untrusted text as a console command).
    uid = getattr(user, "id", None)
    return f"User-{uid}" if isinstance(uid, int) and uid > 0 else "Unknown player"


def minecraft_chat_command(user, body, source="username"):
    """Safe Minecraft 1.21.1 tellraw: never interpolate text as raw commands."""
    name = discord_minecraft_name(user, source)
    payload = {'text': '', 'extra': [
        {'text': '[Discord] ', 'color': 'dark_green'},
        {'text': name, 'color': 'green'},
        {'text': ': ', 'color': 'gray'},
        {'text': str(body), 'color': 'white'},
    ]}
    return 'tellraw @a ' + json.dumps(payload, ensure_ascii=False)
