"""Zygarde | AMP 2 Minecraft <> Discord bridge, Windows 11, Python 3.11+."""

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import time

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from bridge_identity import avatar_url as skin_avatar_url, minecraft_chat_command, load_avatar_overrides

from amp_client import AMPClient, AMPError
from advancement_names import AdvancementResolver
from chat_parser import parse_entry
from formatting import (format_uptime, metric_display, metric_percent,
                        player_count, pretty_state, safe_text, state_code)

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')
(BASE / 'data').mkdir(exist_ok=True)
(BASE / 'logs').mkdir(exist_ok=True)

LOG = logging.getLogger('zygarde')
LOG.setLevel(logging.INFO)
log_format = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
file_handler = RotatingFileHandler(BASE / 'logs' / 'zygarde.log', maxBytes=2_000_000, backupCount=4, encoding='utf-8')
file_handler.setFormatter(log_format)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
LOG.addHandler(file_handler)
LOG.addHandler(console_handler)


def setting(name, fallback='', required=False):
    value = os.getenv(name, fallback).strip()
    if required and not value:
        raise SystemExit(f'Missing {name}: create .env from .env.example and configure it locally.')
    return value


def number(name, fallback=0):
    try:
        return int(setting(name, str(fallback)))
    except ValueError:
        raise SystemExit(f'{name} must be a numeric Discord ID (or blank).') from None


def enabled(name, default='true'):
    return setting(name, default).lower() in {'true', '1', 'yes', 'on'}


TOKEN = setting('DISCORD_TOKEN', required=True)
GUILD_ID = number('DISCORD_GUILD_ID')
CHAT_ID = number('CHAT_CHANNEL_ID')
ALERT_ID = number('ALERT_CHANNEL_ID') or CHAT_ID
DASHBOARD_ID = number('DASHBOARD_CHANNEL_ID') or ALERT_ID
MANAGER_ROLE_ID = number('MANAGER_ROLE_ID')
SERVER_NAME = safe_text(setting('SERVER_NAME', 'Mineverse'), 60) or 'Mineverse'
BRIDGE_TO_MC = enabled('BRIDGE_DISCORD_TO_MC')
USE_WEBHOOK = enabled('USE_WEBHOOK_AVATARS')
USE_AVATARS = enabled('USE_PLAYER_AVATARS')
DISCORD_MC_NAME_SOURCE = setting('DISCORD_MC_NAME_SOURCE', 'username').lower()
if DISCORD_MC_NAME_SOURCE not in {'username', 'display'}:
    raise SystemExit('DISCORD_MC_NAME_SOURCE must be username or display.')
EVENTS_IN_CHAT = enabled('PLAYER_EVENTS_IN_CHAT')
POLL_SECONDS = max(3, number('CHAT_POLL_SECONDS', 4))
DASHBOARD_SECONDS = max(30, number('DASHBOARD_UPDATE_SECONDS', 60))
AMP_URL = setting('AMP_URL', required=True)
AMP_USER = setting('AMP_USERNAME', required=True)
AMP_PASS = setting('AMP_PASSWORD', required=True)
AMP_INSTANCE_ID = setting('AMP_INSTANCE_ID')
# Semicolon-separated Windows paths (mods folder, resource packs, KubeJS assets, or individual JARs).
ADVANCEMENT_LANGUAGE_PATHS = [p.strip().strip('\"') for p in setting('ADVANCEMENT_LANGUAGE_PATHS').split(';') if p.strip()]


if not GUILD_ID or not CHAT_ID:
    raise SystemExit('DISCORD_GUILD_ID and CHAT_CHANNEL_ID must be set.')
if AMP_URL.startswith('http://') and not AMP_URL.startswith(('http://127.0.0.1:', 'http://localhost:', 'http://[::1]:')):
    LOG.warning('AMP_URL uses HTTP outside loopback. Use HTTPS for nonlocal AMP connections.')

amp = AMPClient(AMP_URL, AMP_USER, AMP_PASS, AMP_INSTANCE_ID)
ADVANCEMENTS = AdvancementResolver(ADVANCEMENT_LANGUAGE_PATHS, BASE / 'data' / 'advancement_names.json')
intents = discord.Intents.default()
intents.message_content = True  # Required only for Discord -> MC text
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents,
                   allowed_mentions=discord.AllowedMentions.none())
EMERALD = discord.Color(0x45D588)
DEEP = discord.Color(0x1D845E)
AMBER = discord.Color(0xF4B95B)
RED = discord.Color(0xDC5969)
MUTED = discord.Color(0x33483F)
NO_PINGS = discord.AllowedMentions.none()
DASH_FILE = BASE / 'data' / 'dashboard.json'
try:
    AVATAR_OVERRIDES = load_avatar_overrides(BASE / 'data' / 'player_avatars.json')
except ValueError as exc:
    raise SystemExit(f'Avatar configuration error: {exc}') from exc

current_status = None
current_players = None
last_state = None
planned_stop_until = 0.0
last_crash = 0.0
failed_polls = 0
api_down = False
resource_state = {'CPU': {'streak': 0, 'alert_at': 0.0}, 'RAM': {'streak': 0, 'alert_at': 0.0}}
recent_chat = deque(maxlen=30)
activity_log = deque(maxlen=100)
webhook = None
webhook_unavailable = False
status_poll_at = 0.0
dashboard_message = None
dashboard_lock = asyncio.Lock()
last_manual_dashboard_refresh = 0.0


def redacted(error):
    value = str(error)
    for credential in (TOKEN, AMP_PASS, AMP_USER):
        if credential and len(credential) >= 4:
            value = value.replace(credential, '[REDACTED]')
    return safe_text(value, 250)


def audit(message):
    """Record actions and outages, never chat contents, passwords, or tokens."""
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | {safe_text(message, 350)}"
    activity_log.append(line)
    LOG.info('%s', safe_text(message, 350))


def can_manage(member):
    if not isinstance(member, discord.Member) or member.guild.id != GUILD_ID:
        return False
    return member.guild_permissions.administrator or (
        MANAGER_ROLE_ID > 0 and any(role.id == MANAGER_ROLE_ID for role in member.roles)
    )


def make_embed(title, desc='', color=EMERALD, footer=None):
    embed = discord.Embed(title=safe_text(title, 220), description=desc[:3900],
                          color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text=footer or f'ZYGARDE  •  {SERVER_NAME} / AMP 2')
    return embed


def avatar_url(player):
    # MCHeads renders the skin's pixelated face and outer hat/helmet layer.
    # UUID or texture ID overrides also support offline-mode skin setups.
    return skin_avatar_url(player, AVATAR_OVERRIDES) if USE_AVATARS else None


def status_embed(status, players=None):
    code = state_code(status)
    online = code == 20
    bad = code == 100
    color = EMERALD if online else RED if bad else AMBER if code is not None else MUTED
    label = 'ONLINE' if online else 'OFFLINE / IN TRANSITION' if code is not None else 'AMP UNAVAILABLE'
    embed = make_embed(f'◆ {SERVER_NAME.upper()}  |  LIVE SERVER DASHBOARD',
                       f'**ZYGARDE MONITORING**  •  {label}\n'
                       '━━━━━━━━━━━━━━━━━━━━━━━━━━', color,
                       footer=f'ZYGARDE  •  AMP 2  •  Auto-refresh every {DASHBOARD_SECONDS}s')
    count, maximum = player_count(status, players)
    embed.add_field(name='▰ STATUS', value=f'**{pretty_state(status)}**', inline=True)
    embed.add_field(name='♟ PLAYERS', value=f'**{count}** / {maximum}', inline=True)
    embed.add_field(name='◷ UPTIME', value=f'**{format_uptime(status.get("Uptime") if isinstance(status, dict) else None)}**', inline=True)
    embed.add_field(name='▣ CPU', value=f'**{metric_display(status, "cpu")}**', inline=True)
    embed.add_field(name='▤ MEMORY', value=f'**{metric_display(status, "memory", "ram")}**', inline=True)
    embed.add_field(name='◈ CONNECTION', value='**AMP 2 / Local API**' if status else '**API unreachable**', inline=True)
    if players:
        embed.add_field(name='◉ IN THE WORLD', value=safe_text('  ·  '.join(players[:25]), 1000), inline=False)
    else:
        embed.add_field(name='◉ IN THE WORLD', value='No names reported by AMP', inline=False)
    return embed


async def get_channel(channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            LOG.warning('Discord channel %s unavailable (%s)', channel_id, type(exc).__name__)
            return None
    return channel if isinstance(channel, discord.TextChannel) and channel.guild.id == GUILD_ID else None


async def alert(title, text, level='info'):
    channel = await get_channel(ALERT_ID)
    if channel is None:
        return
    color = {'ok': EMERALD, 'warn': AMBER, 'error': RED, 'info': DEEP}.get(level, DEEP)
    try:
        await channel.send(embed=make_embed(title, safe_text(text, 1800), color), allowed_mentions=NO_PINGS)
    except discord.DiscordException as exc:
        LOG.warning('Could not send alert: %s', type(exc).__name__)


async def get_chat_webhook(channel):
    global webhook, webhook_unavailable
    if webhook_unavailable or not USE_WEBHOOK:
        return None
    if webhook is not None and webhook.channel_id == channel.id:
        return webhook
    try:
        hooks = await channel.webhooks()
        hook = next((h for h in hooks if h.name == 'Zygarde • Minecraft' and h.user and bot.user and h.user.id == bot.user.id), None)
        webhook = hook or await channel.create_webhook(name='Zygarde • Minecraft',
                                                     reason='Display Minecraft users with player avatars')
        return webhook
    except (discord.Forbidden, discord.HTTPException) as exc:
        webhook_unavailable = True
        LOG.warning('Player webhooks unavailable (%s); using embed fallback. Grant Manage Webhooks to enable.', type(exc).__name__)
        return None


async def relay_event(event):
    global last_crash
    kind, player, message = event
    if kind == 'crash':
        now = time.monotonic()
        if now - last_crash < 180:
            return
        last_crash = now
        audit('Possible Minecraft crash line observed')
        await alert('⚠ ZYGARDE  |  CRASH SIGNAL',
                    'Minecraft console reported a possible crash. Check AMP console and crash reports.\n'
                    + safe_text(message, 400), 'error')
        return
    channel = await get_channel(CHAT_ID)
    if channel is None:
        return
    player_name = safe_text(player, 30)
    try:
        if kind == 'chat':
            text = safe_text(message, 1700)
            if not text:
                return
            recent_chat.append(f'<{player_name}> {text[:150]}')
            hook = await get_chat_webhook(channel)
            if hook:
                try:
                    avatar = avatar_url(player)
                    kwargs = {'avatar_url': avatar} if avatar else {}
                    await hook.send(content=text, username=player_name,
                                    allowed_mentions=NO_PINGS, wait=False, **kwargs)
                    return
                except discord.DiscordException as exc:
                    LOG.warning('Webhook delivery failed (%s); falling back to embed.', type(exc).__name__)
            embed = make_embed('MINECRAFT CHAT', text, DEEP, footer=f'{SERVER_NAME}  •  In-game message')
            avatar = avatar_url(player)
            if avatar:
                embed.set_author(name=player_name, icon_url=avatar)
            else:
                embed.set_author(name=player_name)
            await channel.send(embed=embed, allowed_mentions=NO_PINGS)
        elif EVENTS_IN_CHAT and kind in ('join', 'leave', 'death', 'advancement'):
            palette = {'join': (EMERALD, '✦ JOINED THE WORLD'),
                       'leave': (AMBER, '↗ LEFT THE WORLD'),
                       'death': (RED, '☠ PLAYER DEATH'),
                       'advancement': (DEEP, '🏆 ADVANCEMENT')}
            color, heading = palette[kind]
            desc = {
                'join': f'**{player_name}** joined the server',
                'leave': f'**{player_name}** left the server',
                'death': safe_text(message, 250),
                'advancement': f'**{player_name}** completed **{discord.utils.escape_markdown(safe_text(ADVANCEMENTS.resolve(message), 120))}**',
            }[kind]
            event_embed = make_embed(heading, desc, color)
            avatar = avatar_url(player)
            if avatar:
                event_embed.set_thumbnail(url=avatar)
            await channel.send(embed=event_embed, allowed_mentions=NO_PINGS)
    except discord.DiscordException as exc:
        LOG.warning('Minecraft -> Discord relay failed (%s)', type(exc).__name__)


async def check_state(status):
    global last_state
    state = state_code(status)
    if state is None:
        return
    old = last_state
    last_state = state
    if old is None or old == state:
        return
    audit(f'AMP state changed {old} -> {state} ({pretty_state(status)})')
    if state == 20:
        await alert('✦ MINEVERSE ONLINE', 'Minecraft is now online and ready for players.', 'ok')
    elif state == 100:
        await alert('⚠ MINEVERSE FAILED', 'AMP reports that the server failed. Check the console.', 'error')
    elif state == 0:
        planned = time.monotonic() < planned_stop_until or old in {30, 40, 45, 10}
        if not planned and old == 20:
            await alert('⚠ UNEXPECTED STOP', 'Minecraft stopped without a recorded control request. Inspect the AMP console.', 'error')
        else:
            await alert('▣ MINEVERSE STOPPED', 'The Minecraft server has stopped.', 'warn')


async def check_resources(status):
    now = time.monotonic()
    for metric, terms in (('CPU', ('cpu',)), ('RAM', ('memory', 'ram'))):
        val = metric_percent(status, *terms)
        entry = resource_state[metric]
        entry['streak'] = entry['streak'] + 1 if val is not None and val >= 90 else 0
        if entry['streak'] >= 3 and now - entry['alert_at'] >= 900:
            entry['alert_at'] = now
            audit(f'{metric} high usage alert: {val:.0f}%')
            await alert(f'⚠ HIGH {metric} USAGE',
                        f'AMP reports {metric} at {val:.0f}%. Sustained high usage may affect Mineverse.', 'warn')


async def poll_once():
    """Core/GetUpdates must use the same logged-in AMP session each time."""
    global current_status, failed_polls, api_down, status_poll_at
    try:
        updates = await asyncio.to_thread(amp.updates)
        if not isinstance(updates, dict):
            raise AMPError('Core/GetUpdates did not return an object')
        entries = updates.get('ConsoleEntries') or []
        if isinstance(entries, list):
            for entry in entries[:300]:
                event = parse_entry(entry)
                if event:
                    await relay_event(event)
        status = updates.get('Status')
        # Status can be absent/delta; fetch independently only at a modest interval.
        now = time.monotonic()
        if not isinstance(status, dict) and (current_status is None or now - status_poll_at >= 30):
            status = await asyncio.to_thread(amp.status)
            status_poll_at = now
        if isinstance(status, dict):
            current_status = status
            await check_state(status)
            await check_resources(status)
        if api_down:
            audit('AMP API connection recovered')
            await alert('✦ AMP CONNECTION RESTORED', 'Zygarde can read the Minecraft instance again.', 'ok')
        failed_polls = 0
        api_down = False
    except (AMPError, OSError, ValueError, TypeError) as exc:
        failed_polls += 1
        if failed_polls == 1 or failed_polls % 15 == 0:
            LOG.warning('Minecraft polling error: %s', redacted(exc))
        if failed_polls == 3:
            api_down = True
            audit('Lost AMP API connection after repeated failures')
            await alert('⚠ AMP CONNECTION LOST', 'Zygarde cannot reach AMP. Local host, credentials, and instance API should be checked.', 'error')
    except Exception as exc:
        failed_polls += 1
        LOG.error('Unexpected polling failure (%s)', type(exc).__name__)
        if failed_polls == 3:
            api_down = True
            audit('AMP polling failed repeatedly')
            await alert('⚠ AMP MONITORING FAILED', 'Check the local Zygarde log for details.', 'error')


async def get_fresh_data():
    global current_status, current_players
    status = await asyncio.to_thread(amp.status)
    if not isinstance(status, dict):
        raise AMPError('AMP status was not an object')
    current_status = status
    try:
        current_players = await asyncio.to_thread(amp.players)
    except (AMPError, OSError, ValueError):
        current_players = None
    return status, current_players


def dashboard_record():
    try:
        value = json.loads(DASH_FILE.read_text(encoding='utf-8'))
        if value.get('channel_id') == DASHBOARD_ID:
            return int(value['message_id'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return None


def save_dashboard(message):
    contents = {'channel_id': message.channel.id, 'message_id': message.id}
    temp = DASH_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(contents, indent=2), encoding='utf-8')
    temp.replace(DASH_FILE)


async def sync_dashboard(force=False):
    """Edits one saved message across restarts, not a new message every minute."""
    global dashboard_message
    async with dashboard_lock:
        channel = await get_channel(DASHBOARD_ID)
        if channel is None:
            return None
        try:
            status, players = await get_fresh_data()
            display = status_embed(status, players)
        except Exception as exc:
            LOG.warning('Dashboard data unavailable: %s', redacted(exc))
            display = status_embed(None)
        if dashboard_message is None or dashboard_message.channel.id != channel.id:
            stored = dashboard_record()
            if stored:
                try:
                    dashboard_message = await channel.fetch_message(stored)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    dashboard_message = None
        try:
            if dashboard_message is not None:
                await dashboard_message.edit(embed=display, view=DashboardView())
            else:
                dashboard_message = await channel.send(embed=display, view=DashboardView(), allowed_mentions=NO_PINGS)
                save_dashboard(dashboard_message)
                audit(f'Live dashboard created in channel {channel.id}')
            return dashboard_message
        except discord.DiscordException as exc:
            LOG.warning('Dashboard could not be updated (%s)', type(exc).__name__)
            return None


class ConfirmControl(discord.ui.View):
    """Destructive action confirmation tied to original staff member (expires)."""
    def __init__(self, action, requester_id):
        super().__init__(timeout=40)
        self.action = action
        self.requester_id = requester_id

    @discord.ui.button(label='Confirm action', style=discord.ButtonStyle.danger, emoji='⚠')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        global planned_stop_until
        if interaction.user.id != self.requester_id or not can_manage(interaction.user):
            return await interaction.response.send_message('You are not authorized to confirm this action.', ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            # Controls act on the configured Minecraft instance only, never ADS.
            action = {'stop': amp.stop, 'restart': amp.restart}[self.action]
            result = await asyncio.to_thread(action)
            if isinstance(result, dict) and (result.get('Status') is False or result.get('success') is False):
                raise AMPError('AMP rejected the control request')
            planned_stop_until = time.monotonic() + 240
            audit(f'{self.action.upper()} requested by Discord user {interaction.user.id}')
            await interaction.followup.send(f'**{self.action.title()}** request sent to Mineverse.', ephemeral=True)
            await alert('▣ STAFF ACTION', f'{self.action.title()} requested by staff.', 'info')
        except Exception as exc:
            audit(f'{self.action.upper()} request failed')
            LOG.warning('Control error: %s', redacted(exc))
            await interaction.followup.send('AMP could not process the request. Check the local bot log.', ephemeral=True)
        for child in self.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.DiscordException:
            pass
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            return await interaction.response.send_message('Only the requester can cancel this.', ephemeral=True)
        await interaction.response.edit_message(content='Cancelled.', view=None)
        self.stop()


async def ask_control(interaction, action):
    if not can_manage(interaction.user):
        return await interaction.response.send_message('Staff-only action.', ephemeral=True)
    await interaction.response.send_message(
        f'⚠ Confirm **{action.upper()}** for **{SERVER_NAME}**? This will affect online players.',
        view=ConfirmControl(action, interaction.user.id), ephemeral=True)


async def start_server(interaction):
    if not can_manage(interaction.user):
        return await interaction.response.send_message('Staff-only action.', ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    try:
        result = await asyncio.to_thread(amp.start)
        if isinstance(result, dict) and (result.get('Status') is False or result.get('success') is False):
            raise AMPError('AMP rejected the start request')
        audit(f'START requested by Discord user {interaction.user.id}')
        await interaction.followup.send('**Start** request sent to Mineverse.', ephemeral=True)
        await alert('▣ STAFF ACTION', 'Start requested by staff.', 'info')
    except Exception as exc:
        LOG.warning('Start control failed: %s', redacted(exc))
        await interaction.followup.send('Start failed. Check the local bot log.', ephemeral=True)


class DashboardView(discord.ui.View):
    """Persistent controls; dispatch after bot restart, with permission checks on every click."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Refresh', emoji='🔄', style=discord.ButtonStyle.secondary, custom_id='zygarde:v1:refresh')
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        global last_manual_dashboard_refresh
        if time.monotonic() - last_manual_dashboard_refresh < 15:
            return await interaction.response.send_message('Dashboard was just refreshed. Try again shortly.', ephemeral=True)
        last_manual_dashboard_refresh = time.monotonic()
        await interaction.response.defer(ephemeral=True)
        msg = await sync_dashboard(force=True)
        await interaction.followup.send('Dashboard refreshed.' if msg else 'Dashboard update failed. Check bot logs.', ephemeral=True)

    @discord.ui.button(label='Players', emoji='👥', style=discord.ButtonStyle.secondary, custom_id='zygarde:v1:players')
    async def players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_players(interaction)

    @discord.ui.button(label='Start', emoji='▶️', style=discord.ButtonStyle.success, custom_id='zygarde:v1:start')
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_server(interaction)

    @discord.ui.button(label='Restart', emoji='🔁', style=discord.ButtonStyle.primary, custom_id='zygarde:v1:restart')
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ask_control(interaction, 'restart')

    @discord.ui.button(label='Stop', emoji='⏹️', style=discord.ButtonStyle.danger, custom_id='zygarde:v1:stop')
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ask_control(interaction, 'stop')


async def show_players(interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        players = await asyncio.to_thread(amp.players)
        display = '\n'.join(f'▰ **{safe_text(n, 18)}**' for n in players[:60]) or 'No players reported by AMP.'
        embed = make_embed(f'♟ {SERVER_NAME.upper()} | ONLINE PLAYERS', display, DEEP,
                           footer=f'ZYGARDE  •  {len(players)} players reported by AMP')
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        LOG.warning('Players request failed: %s', redacted(exc))
        await interaction.followup.send('Could not load player list from AMP.', ephemeral=True)


@tasks.loop(seconds=4)
async def watch_minecraft():
    await poll_once()


@watch_minecraft.before_loop
async def before_watch():
    await bot.wait_until_ready()
    try:
        # Clear historical entries once; keep reading this SAME session thereafter.
        await asyncio.to_thread(amp.updates)
        s = await asyncio.to_thread(amp.status)
        if isinstance(s, dict):
            global current_status, last_state
            current_status = s
            last_state = state_code(s)
        LOG.info('AMP connection OK; Mineverse state: %s; chat bridge active.', pretty_state(s))
        audit('AMP Minecraft monitoring started')
    except Exception as exc:
        LOG.warning('Initial AMP connection failed: %s', redacted(exc))


@tasks.loop(seconds=60)
async def update_dashboard():
    await sync_dashboard()


@update_dashboard.before_loop
async def before_dashboard():
    await bot.wait_until_ready()
    await asyncio.sleep(3)


@bot.event
async def setup_hook():
    bot.add_view(DashboardView())
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)
    LOG.info('Synced %d slash commands to guild %s', len(synced), GUILD_ID)


@bot.event
async def on_ready():
    LOG.info('Zygarde connected to Discord as %s', bot.user)
    if not watch_minecraft.is_running():
        watch_minecraft.change_interval(seconds=POLL_SECONDS)
        watch_minecraft.start()
    if not update_dashboard.is_running():
        update_dashboard.change_interval(seconds=DASHBOARD_SECONDS)
        update_dashboard.start()


@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id or message.guild is None:
        return
    if message.guild.id != GUILD_ID or not BRIDGE_TO_MC or message.channel.id != CHAT_ID:
        return
    if not message.content or not message.content.strip():
        return
    # Never relay commands: tellraw JSON protects Minecraft console from user input.
    body = safe_text(message.content, 180)
    if not body:
        return
    command = minecraft_chat_command(message.author, body, DISCORD_MC_NAME_SOURCE)
    try:
        await asyncio.to_thread(amp.send_minecraft, command)
    except Exception as exc:
        LOG.warning('Discord -> Minecraft chat failed: %s', redacted(exc))


# Existing six commands kept intact for a drop-in replacement.
@bot.tree.command(name='status', description='Show Mineverse live state and AMP metrics')
async def status_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        status, players = await get_fresh_data()
        await interaction.followup.send(embed=status_embed(status, players), ephemeral=True)
    except Exception as exc:
        LOG.warning('Status command failed: %s', redacted(exc))
        await interaction.followup.send('Could not retrieve Mineverse status from AMP.', ephemeral=True)


@bot.tree.command(name='players', description='Show online players reported by AMP')
async def players_cmd(interaction: discord.Interaction):
    await show_players(interaction)


@bot.tree.command(name='recentchat', description='Last 30 Minecraft chat messages observed')
async def recent_chat_cmd(interaction: discord.Interaction):
    body = '\n'.join(recent_chat) or 'No in-game chat recorded since bot startup.'
    await interaction.response.send_message(
        embed=make_embed('≡ MINEVERSE | RECENT CHAT', body[-2700:], DEEP), ephemeral=True)


@bot.tree.command(name='start', description='Start Minecraft (staff only)')
async def start_cmd(interaction: discord.Interaction):
    await start_server(interaction)


@bot.tree.command(name='stop', description='Stop Minecraft (staff only, confirmation required)')
async def stop_cmd(interaction: discord.Interaction):
    await ask_control(interaction, 'stop')


@bot.tree.command(name='restart', description='Restart Minecraft (staff only, confirmation required)')
async def restart_cmd(interaction: discord.Interaction):
    await ask_control(interaction, 'restart')


@bot.tree.command(name='dashboard', description='Publish or refresh the one live Mineverse dashboard (staff only)')
async def dashboard_cmd(interaction: discord.Interaction):
    if not can_manage(interaction.user):
        return await interaction.response.send_message('Staff-only action.', ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    msg = await sync_dashboard(force=True)
    await interaction.followup.send(f'Dashboard ready: {msg.jump_url}' if msg else 'Dashboard update failed. Check the log.', ephemeral=True)


@bot.tree.command(name='logs', description='Recent Zygarde alerts and staff actions (staff only)')
async def logs_cmd(interaction: discord.Interaction):
    if not can_manage(interaction.user):
        return await interaction.response.send_message('Staff-only action.', ephemeral=True)
    entries = list(activity_log)[-12:]
    body = '\n'.join(entries) if entries else 'No recent events since this bot started.'
    await interaction.response.send_message(embed=make_embed('≡ ZYGARDE | STAFF AUDIT LOG',
                                                             body[-3500:], MUTED), ephemeral=True)


if __name__ == '__main__':
    bot.run(TOKEN, log_handler=None)
