# Zygarde 2.1 — Mineverse operations upgrade

**New in this version:** AMP-backed backup inventory monitoring and missing-backup alerts, spark TPS/MSPT monitoring in the live Discord dashboard, and **opt-in** daily restarts with 15/5/1-minute warnings, backup safety gate, and restart deduplication.

- `/backups` (staff only), `/performance`, and `/schedule` are new; the earlier slash commands, avatar chat bridge and working ADS proxy remain unchanged.
- The backup schedule itself must be created once in **AMP 2's Scheduler**. The bot only checks and alerts on actual AMP backup results, and never copies a live world or deletes backups.
- Restarting is **disabled by default**. Enable only after a real test backup. See [Operations and safety setup](docs/OPERATIONS.md).
- Real TPS/MSPT require the server-side **spark** mod. No mod: metrics show `Not available`.
- Run `python -m unittest discover -s tests -v` for offline validation.

---

# Zygarde — AMP 2 Minecraft ↔ Discord Bot

A Python Discord companion for a **single Minecraft Java server managed by CubeCoders AMP 2**. Built and tested for **Windows 11**, using the local AMP ADS proxy — no public AMP port, RCON, or Minecraft bot account required.

> **Security:** Never commit `.env`, server logs, bot tokens, AMP passwords, or player data. Rotate any credential that has been exposed. This repository only contains example configuration.

## Features

| Feature | Details |
| --- | --- |
| **Two-way chat** | Minecraft ↔ Discord with player usernames and Minecraft head avatars |
| **Live dashboard** | One automatically edited status message: players, uptime, CPU, memory, and server state |
| **Admin buttons** | Start / stop / restart with role checks and confirmation for destructive actions |
| **Alerts** | State changes, suspected crashes, disconnects, recovery, and sustained resource warnings |
| **Events** | Player joins/leaves, deaths, and advancements when visible in console output |
| **Audit logs** | Staff-only `/logs`, local rotating event logs, no chat contents in audit history |
| **Customization** | Zygarde emerald embed color, configurable channels, avatars, and polling |

Supports Minecraft Java instances managed through AMP 2 (mod-loader-specific console formats may require `chat_parser.py` adjustments).

## Installation (Windows PowerShell)

1. Install Python 3.11+ and download/clone the repository.
2. In the repository folder, create your own local config with `Copy-Item .env.example .env`.
3. Fill in the **new** Discord bot token, channel IDs, AMP credentials, and ADS instance ID in `.env`. Never commit or send that file.
4. Enable **Message Content Intent** for the bot and give it channel permissions. `Manage Webhooks` in the Minecraft chat channel is optional but enables authentic player-name/avatar messages.
5. Run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe check_amp.py
.\.venv\Scripts\python.exe bot.py
```

**AMP ADS proxy configuration** (replace the ID with your own — this is not the dashboard URL):

```dotenv
AMP_URL=http://127.0.0.1:8080
AMP_INSTANCE_ID=YOUR_INSTANCE_ID
```

**Do not port-forward AMP's management port.** Keep the bot and AMP on the same PC when using `127.0.0.1`.

**Full setup guide:** [docs/SETUP.md](docs/SETUP.md).

## Discord commands

`/status` · `/players` · `/recentchat` · `/start` · `/stop` · `/restart` · `/dashboard` · `/logs`

Server control commands require a Discord administrator or the role specified by `MANAGER_ROLE_ID`; destructive actions ask for confirmation. Discord messages are sanitized and bridged using Minecraft `tellraw` JSON instead of raw arbitrary console commands.

## How chat avatars work

Minecraft → Discord messages use Discord webhooks, when permitted, and show heads provided by [MCHeads](https://mc-heads.net/). If a skin does not resolve by username, create `data/player_avatars.json` from the included `data/player_avatars.example.json` and supply the UUID or texture ID. The real `data/player_avatars.json` file is gitignored.

Third-party avatar services receive the player name or UUID to render the head. Disable `USE_PLAYER_AVATARS` and `USE_WEBHOOK_AVATARS` in your local `.env` if you prefer not to use them.

## Development

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The GitHub Actions workflow runs offline unit tests. Live Discord/AMP integration requires your own running server and is not tested in CI.

## Publishing safely

See [docs/GITHUB.md](docs/GITHUB.md) and [SECURITY.md](SECURITY.md). Repository examples contain no live credentials. Review the staged files before publishing, especially if you have copied a working `.env` or local data into this folder.

## License

No open-source license has been selected yet. If you want other people to reuse or modify the source, choose a license (for example MIT) and add a `LICENSE` file before publication. Public visibility alone is not an open-source license.

## References

- [CubeCoders AMP API developer guide](https://github.com/CubeCoders/AMP/wiki/Developers:-How-do-I-start-working-with-AMP's-API%3F)
- [discord.py documentation](https://discordpy.readthedocs.io/en/stable/)
- [MCHeads](https://mc-heads.net/)
