"""Choose Discord destinations for Minecraft console events.

Separate from Discord APIs to make routing testable without a network connection.
"""


def event_channel_id(kind, chat_id, player_events_id=None, events_enabled=True):
    """Return a channel ID, or None when a non-chat event is disabled."""
    if kind == 'chat':
        return chat_id
    if not events_enabled:
        return None
    if kind == 'advancement':
        return chat_id
    if kind in {'join', 'leave', 'death'}:
        return player_events_id or chat_id
    return None
