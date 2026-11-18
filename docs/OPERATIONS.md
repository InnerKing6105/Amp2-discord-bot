# Operations: AMP backups, spark, and scheduled restarts

This bot runs **on your Windows 11 computer alongside AMP 2**. It uses your existing local ADS proxy (`AMP_URL=http://127.0.0.1:8080` and `AMP_INSTANCE_ID=<your actual instance ID>`). No router port forwarding is required.

## 1. Automatic backups (managed by AMP; monitored by Zygarde)

Zygarde **does not make copies of live world files itself**. AMP supports consistent Minecraft backups and already has a built-in scheduler. We intentionally use AMP's backup mechanism rather than introducing a second backup procedure.

One-time setup in AMP 2:

1. Log in to AMP and **Manage your Minecraft instance** (not ADS01).
2. Open **Backups**, make one manual test backup, and verify it finishes and can be listed.
3. Open **Scheduler** in that Minecraft instance. Create a new *daily* time trigger, e.g. **04:00** local time.
4. Add the action under **Backups → Take a backup** (wording may differ by AMP version). For AMP versions that provide these controls, use a consistent Minecraft backup method and appropriate storage/retention settings.
5. Run the scheduled task once, confirm a new entry appears under Backups, and ensure you have enough disk space. Store at least one off-PC copy for disaster recovery; Zygarde does not send world backups to Discord or GitHub.
6. Keep `BACKUP_MONITOR_ENABLED=true` in your private `.env`. Zygarde calls `LocalFileBackupPlugin/GetBackups` (if allowed by your AMP version/permissions). The `/backups` staff-only command shows the most recently **verified** item. A warning is sent if AMP does not report a backup newer than `BACKUP_MAX_AGE_HOURS` (default 26 hours). Zygarde does not claim a backup succeeded just because its scheduled time passed.

If `/backups` reports that the inventory is unavailable, ensure AMP's `LocalFileBackupPlugin` is loaded and that the bot's AMP account has read access. Some AMP versions or configurations can expose different API results; use the instance's own `/API` browser to verify.

**Avoid setting up a second backup schedule in the bot**—AMP should be the single backup scheduler. Check backup restores periodically.

## 2. TPS / MSPT monitoring using spark

1. Ensure the [spark](https://spark.lucko.me/) mod/plugin is installed **server-side** and compatible with your Minecraft loader and version (Fabric, NeoForge, etc.).
2. In AMP's Minecraft console, run `spark tps` (no leading slash). It should print lines beginning `TPS from last...` and `Tick durations ...`.
3. Set `PERFORMANCE_MONITOR_ENABLED=true` (already the example default). Zygarde requests `spark tps` every 180 seconds, reads the resulting AMP `Core/GetUpdates` console stream, and displays **1-minute TPS** and **10-second median/p95 MSPT** when available. The `/performance` command requests a new sample; dashboard shows `Not available` if spark is missing or no parsable reply is returned.
4. Tune `PERFORMANCE_WARN_TPS` and `PERFORMANCE_WARN_MSPT`. Three consecutive poor samples trigger a warning, with a cooldown to prevent spam.

Normal Minecraft TPS is near 20. MSPT is in milliseconds per game tick; 50ms is the nominal tick budget. These measurements are not invented from CPU/RAM readings.

## 3. Scheduled restarts (opt-in)

Do **not** enable until you have tested AMP backups and the bot's AMP account is authorized to restart the Minecraft instance.

Edit only your **private** `.env`:

```env
RESTART_ENABLED=true
RESTART_TIMEZONE=America/Toronto
RESTART_AT=05:00
RESTART_REQUIRE_RECENT_BACKUP=true
BACKUP_MAX_AGE_HOURS=26
```

- At 04:45, 04:55, and 04:59 local time, Zygarde sends in-game warnings; the first warning also appears in the Discord alerts channel.
- At 05:00, it asks AMP to restart **only if Minecraft is online** and, if enabled, AMP reports a recent backup.
- It remembers the date in `data/restart_state.json` and will not issue a second automatic restart that day, even if the bot reconnects. If Zygarde is down or launched several minutes after the time, it **skips** the missed restart rather than unexpectedly restarting later.
- To suspend automation instantly, change `RESTART_ENABLED=false` and restart the bot. Use `/schedule` to view the settings.
- The process must remain running for scheduling to function. Use Windows Task Scheduler or other trusted process supervision to start the bot after login/reboot. AMP's built-in scheduler can also restart the server independently; **avoid configuring both restart schedulers** for the same time.

## 4. Commands and permissions

| Command | Access | Purpose |
| --- | --- | --- |
| `/performance` | Server members | Reads spark TPS / MSPT; no server control |
| `/backups` | AMP/Discord staff role or Discord administrator | Read-only AMP backup inventory |
| `/schedule` | Server members | Display next configured daily restart time |
| `/status`, `/players`, `/recentchat`, `/dashboard`, `/start`, `/stop`, `/restart`, `/logs` | Unchanged | Existing commands and their existing authorization |

Only staff can operate start/stop/restart. Automated restart is off by default. The bot never deletes, restores, or downloads world backups.

## 5. Troubleshooting

- `/backups` unavailable: check AMP backup plugin permissions and the Minecraft instance's API browser; ensure ADS proxy is still the working URL.
- Blank TPS/MSPT: verify `spark tps` output in AMP console. Some mods/logging configs filter the console; the bot then displays unavailable rather than a fictitious number.
- Scheduled restart skipped: check recent backup age, online state, local timezone, and the bot log. The bot marks attempts for that day to prevent retry loops.
- Lost API connection: keep `AMP_URL` on `127.0.0.1` when the bot runs on the same Windows machine, and rotate previously exposed credentials.
- Any backup/restore operation should be tested on a copied world before depending on it.

Source references: [AMP official site (scheduler/backups)](https://www.cubecoders.com/AMP), [AMP developer API guide](https://github.com/CubeCoders/AMP/wiki/Developers:-How-do-I-start-working-with-AMP's-API%3F), [spark TPS/MSPT docs](https://spark.lucko.me/docs/guides/TPS-and-MSPT).
