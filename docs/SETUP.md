# Detailed setup and troubleshooting


**Windows 11 · Python 3.11+ · CubeCoders AMP 2 · Minecraft Java / Fabric or NeoForge**

Single-server bot. Does **not** need Minecraft RCON, Minecraft player login, public AMP ports, or router port forwarding. All AMP calls go over your existing local ADS proxy; Discord connection is outgoing.

## Latest fix: accurate avatars and Discord usernames

This version fixes the two problems in the screenshot:

1. **Discord → Minecraft:** An older bot version stripped *all non-ASCII characters* from server nicknames. A nickname made of stylized Unicode letters could become an empty string, which displayed `Discord user`. This version uses the actual **Discord account username** (`message.author.name`) by default, so Mineverse sees `[Discord] exampleuser: hello` instead of `[Discord] Discord user: hello`. It uses a subtle green `[Discord]` label and a safe `tellraw` JSON component (not an executable user command).
2. **Minecraft → Discord:** Player avatars now use **MCHeads** 96-pixel player skin faces, including hat/helmet layers, rather than Minotar. The avatar is shown on Minecraft chat webhooks and join/leave/death/advancement notifications. Minecraft usernames are resolved by MCHeads; use an override for offline-mode/custom skins if the wrong face appears.

### If a player still has the default Steve/Alex avatar

MCHeads can render a registered Minecraft Java player's real skin using the username or UUID. If your Mineverse player uses a *different Minecraft identity*, offline-mode UUID, or a custom skin not registered to that name, public skin services cannot know the actual skin automatically.

To force a particular player's correct skin, copy `data/player_avatars.example.json` to **`data/player_avatars.json`** in the new bot folder, and replace its entry with a player-name-to-**actual Mojang UUID or skin texture ID** mapping, for example:

```json
{
  "YourMinecraftName": "YOUR_REAL_MOJANG_UUID_OR_SKIN_TEXTURE_ID"
}
```

Use the real 32-hex-character UUID or the 64-hex-character skin texture ID, not the placeholder above. MCHeads accepts usernames, UUIDs, Floodgate UUIDs and skin texture IDs. It recommends UUIDs over names for accuracy. Look up the Java account UUID from the official Minecraft profile service, or obtain the texture ID from the player's skin texture URL if they use a custom skin. **Do not use someone else's UUID** unless you intend to show that person's skin. The override is optional: do not copy the example if the default looks right.

After changing `player_avatars.json`, restart the bot. Only **new chat messages** use the updated image; past Discord webhook avatars may stay cached. MCHeads and Discord can cache images, so a newly changed skin may not display immediately.

### Choosing the name sent to Minecraft

Leave this in `.env` for the real Discord account username:

```env
DISCORD_MC_NAME_SOURCE=username
```

If you prefer server nicknames, use `DISCORD_MC_NAME_SOURCE=display`. This also allows non-ASCII nicknames, but some stylized symbols might not appear in every Minecraft font. **`username` is recommended** for clear player names.

## What's new

- One **live dashboard** (dark Discord UI + emerald/green embed border), automatically posted to `DASHBOARD_CHANNEL_ID` (or the alerts channel), **edited every 60 seconds** instead of repeatedly posting messages. Restores the message ID after restarts using `data/dashboard.json`. State, players, uptime, CPU and RAM shown only if AMP exposes them.
- **Persistent buttons**: Refresh, Players, Start, Restart, Stop. Everyone can read status; only server administrators or `MANAGER_ROLE_ID` can execute controls. Stop and restart require a requester-bound, expiring confirmation. Buttons survive bot restarts.
- Minecraft messages appear under the player's **name and skin avatar** using a Discord webhook (when granted **Manage Webhooks** in the chat channel). Otherwise, gracefully falls back to compact emerald Discord embeds with player avatar icons. Uses Minotar for skins; you can disable third-party avatar lookup.
- Player **join, leave, death, and advancement** messages get short styled event cards (when identifiable from AMP console output).
- Discord → Minecraft continues via `tellraw` JSON text, not raw commands. Incoming webhook/bot messages never echo back to Minecraft.
- Alerts for **online, stopped, failed, likely crash**, lost/recovered AMP connectivity, and sustained 90%+ CPU/RAM usage (only if AMP exposes percentages). Repeated alerts are suppressed.
- Rotating local `logs/zygarde.log`, staff-only `/logs` for recent action/outage audit events. Chat text is **not stored in the audit log**. `/recentchat` keeps a small in-memory list of Minecraft chat during a running process.

### Existing commands preserved

`/status`, `/players`, `/recentchat`, `/start`, `/stop`, `/restart`.

### New commands

`/dashboard` (staff) — create/refresh the persistent dashboard in the configured status channel.

`/logs` (staff) — view recent control and state events, only visible to the requesting staff member.

## Update your existing installation (without losing the working connection)

1. **Rotate the previously exposed Discord bot token and AMP password first.** Treat the old values as compromised. Never paste your `.env` into chat. Create a separate, least-privilege AMP account for the bot if practical.
2. Stop your existing Zygarde bot (`Ctrl+C`). Keep your old folder as a backup.
3. Extract this ZIP into a **new folder**. The ZIP intentionally has **no real `.env`** file.
4. Copy your working `.env` from the old bot folder into the new bot folder **only after updating it with the newly rotated credentials**. Or copy `.env.example` to `.env` and fill it in manually.
5. Keep your known-good AMP settings for the local ADS connection:

   ```env
   AMP_URL=http://127.0.0.1:8080
   AMP_INSTANCE_ID=YOUR_INSTANCE_ID
   ```

   These are the *instance routing settings*, **not passwords**. Leave the rest of the working AMP configuration unchanged.

6. To get separate status, alerts, and chat channels, add optional settings to your `.env`:

   ```env
   DASHBOARD_CHANNEL_ID=YOUR_SERVER_STATUS_CHANNEL_ID
   ALERT_CHANNEL_ID=YOUR_ALERT_CHANNEL_ID
   USE_WEBHOOK_AVATARS=true
   USE_PLAYER_AVATARS=true
   PLAYER_EVENTS_IN_CHAT=true
   DASHBOARD_UPDATE_SECONDS=60
   ```

   If `DASHBOARD_CHANNEL_ID` is blank or missing, the dashboard goes to the alerts channel (or chat channel if no alerts channel is set). Start with a dedicated `#server-status` text channel if you can.

7. From PowerShell inside the **new** folder:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   .\.venv\Scripts\python.exe check_amp.py
   .\.venv\Scripts\python.exe bot.py
   ```

   Later you can double-click `start.bat` to run the bot. **Do not run both copies simultaneously**: two bot processes will race to read `Core/GetUpdates` and can send duplicate events.

8. Once Discord says Zygarde is online, use `/status` and `/dashboard`. It will make or update **one** dashboard message. You can pin that message manually in the Discord channel.

## Discord permissions

Invite your existing bot with the `bot` and `applications.commands` scopes; no need to create a new application.

The bot requires in the appropriate channels:
- **View Channel**, **Send Messages**, **Embed Links**, **Read Message History**.
- **Manage Webhooks** **in `#minecraft-chat` only**, optional but recommended to show each Minecraft player as a separate sender with a skin avatar. Do not grant Administrator permission to the bot.
- In the Discord Developer Portal → Bot, enable **Message Content Intent** for Discord-to-Minecraft messages.
- You must have **Discord server Administrator permission**, or you must configure your staff role ID in `MANAGER_ROLE_ID`, to control the server. Everyone else sees a private denial.

## Test in order

1. `check_amp.py` succeeds and prints the correct instance state (not the ADS controller).
2. `/status` shows the Mineverse state, and `/dashboard` posts one status card. Wait over a minute; **same message should edit**, not spam a new message.
3. Join Mineverse; send `hello from Minecraft` in game. The text appears in `#minecraft-chat` with your player name and avatar (or embed fallback).
4. Send `hello from Discord` in `#minecraft-chat`. The message appears in-game. It should **not bounce back** to Discord in an infinite loop.
5. Use `/players`; use a server admin account to press Start, Restart or Stop, with confirmation on the destructive actions.
6. Check alerts and `/logs` after a restart, stop or disconnection. Do not deliberately crash your server to test the alert.

## How it works / limitations

- **No port forwarding**: Python bot and AMP 2 run on the same Windows PC using `http://127.0.0.1:8080` + AMP's ADS instance proxy. Do *not* expose AMP 8080 to the internet.
- Uses `Core/Login`, `Core/GetUpdates`, `Core/GetStatus`, `Core/GetUserList`, `Core/SendConsoleMessage`, `Core/Start`, `Core/Stop`, `Core/Restart`. Console updates are read **for the same API session**, approximately every 4s. On startup, the first backlog is intentionally ignored so old chat won't flood Discord.
- **Chat parsing** depends on the console format for your mod loader and mods. A modded chat plugin that changes log format may need `chat_parser.py` adjustments. Some AMP configurations don't return all online usernames or percentage metrics, so missing values correctly show “Not available”.
- Only messages from actual players logged by AMP can be forwarded as in-game chat; the bot does not read private messages outside of AMP's console.
- Player avatars use `https://mc-heads.net/avatar/<player>/96.png` which sends Minecraft player names to MCHeads/Discord (both external services). Set `USE_PLAYER_AVATARS=false` and `USE_WEBHOOK_AVATARS=false` for privacy or if avatars don't load. If Manage Webhooks is missing, it automatically uses embeds instead.
- Webhook identities represent **Minecraft messages**, not verified Discord members. Minecraft users do not have Discord permissions through these webhook names.
- Discord doesn't allow bots to choose arbitrary background colors for embeds. The green embed accent, dark-looking layout, and UI copy make the Zygarde theme fit Discord's dark mode.
- Staff action/event logs are local, rotated. The `/logs` command shows only *recent in-process* events; longer logs are in `logs/zygarde.log`.
- Currently no backup command, TPS promise, automatic restarts, or Minecraft-side statistic collection; such features need separate AMP/plugin validation.

## Security notes

- `.env` is excluded from git and **not included in the ZIP**. IDs and routing paths are not passwords, but credentials are secret.
- Discord messages are sanitized and passed to `tellraw` as JSON. Non-staff users cannot execute console commands through bridge chat.
- Manager permissions are re-checked **at button click time**, including after bot restarts. Stop/Restart confirmations are short-lived and bound to the requesting member.
- Resource/crash alerts are best-effort, not a replacement for backups or server monitoring.

## Avatar and Discord username sources

- MCHeads player avatar API: https://mc-heads.net/ (UUIDs are recommended over names)
- discord.py User.name / Member.display_name: https://discordpy.readthedocs.io/en/latest/api.html
- Minecraft 1.21.1 tellraw command: https://minecraft.wiki/w/Commands/tellraw

## Documentation used

- AMP API developer guide: https://github.com/CubeCoders/AMP/wiki/Developers:-How-do-I-start-working-with-AMP's-API%3F
- AMP `GetUpdates` API: https://docs.rs/ampapi/latest/src/ampapi/modules/core.rs.html
- discord.py persistent views example: https://github.com/Rapptz/discord.py/blob/master/examples/views/persistent.py
- Discord webhook reference: https://discordpy.readthedocs.io/en/latest/api.html
