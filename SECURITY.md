# Security policy

## Reporting vulnerabilities

Please avoid posting bot tokens, credentials, private logs, or server addresses in public GitHub issues. Report suspected vulnerabilities to the repository owner privately through GitHub private vulnerability reporting (if enabled).

## Deployment guidelines

- Never commit `.env`; copy `.env.example` to `.env` locally.
- Rotate your Discord token and AMP password if they have ever been posted to a chat, issue, or repository. Removing a leaked token from Git history is **not** a substitute for revoking it.
- Do not expose AMP's ADS/API web interface to the public internet. This bot uses the loopback address when it is on the same machine as AMP.
- Give the bot only Discord permissions it needs. Limit **Manage Webhooks** to the Minecraft chat channel; do not grant Discord Administrator to the bot itself.
- Give Minecraft start/stop/restart permission only to trusted Discord members or a private manager role.
- Avoid copying `logs/`, `data/dashboard.json`, `data/player_avatars.json`, or game/server configuration files into the repository.
- Check any commits you stage with `git diff --cached` before you push; enable GitHub push protection where available.
- Public Minecraft chat messages and player names may be sent to Discord and avatar providers. Tell players what the bridge does.

## Automatic operations (v2.1)

- `RESTART_ENABLED=false` is the secure default. Enable only after verified backups and check `RESTART_REQUIRE_RECENT_BACKUP=true`.
- Zygarde does not create or restore backups. AMP's built-in scheduler owns backup consistency and retention. The bot reads inventory only.
- Metrics are parsed only from spark console output and are never substituted from unrelated RAM/CPU fields.
- Files under `data/`, including restart and dashboard state, are ignored by Git and should remain private.
