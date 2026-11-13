# Publish Zygarde to GitHub

These steps are for **Windows PowerShell**. You control whether the new repository is public or private.

## Before starting

1. Rotate any credentials ever shared outside your PC. Keep your newly rotated token and AMP password in `.env` **only**.
2. Review `.gitignore`; avoid adding any logs, local data files, backups or private server files.
3. For your first upload, GitHub recommends creating an **empty** repository: no GitHub-generated README, license or `.gitignore` (this package already includes its own).
4. Decide whether you want to publish a license. No license is supplied automatically.

## Upload using Git

Create a new empty repo at https://github.com/new, such as `zygarde-amp2-discord-bot`.

Open PowerShell **in the extracted bot project folder**, then:

```powershell
git init
git branch -M main
git add .env.example .gitignore .github README.md SECURITY.md docs requirements.txt bot.py amp_client.py bridge_identity.py chat_parser.py check_amp.py formatting.py start.bat tests data/.gitkeep data/player_avatars.example.json logs/.gitkeep
git status --short
git diff --cached --name-only
git diff --cached
git commit -m "Initial Zygarde AMP 2 Discord bot"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/zygarde-amp2-discord-bot.git
git push -u origin main
```

**Before `git commit`:** inspect the output of `git diff --cached` for anything private. If you have added screenshots or personal identifiers, remove them from the commit first.

If `git remote add origin` reports a remote already exists, inspect `git remote -v` and update it only if necessary with `git remote set-url origin YOUR_URL`.

If GitHub asks for authentication, sign in using GitHub Desktop, GitHub CLI, or a supported Git credential manager; never paste your GitHub password/token into chat.

## Upload without Git

You can also create a repository on GitHub, choose **Add file → Upload files**, and upload the files **other than** `.env`, `data/dashboard.json`, `data/player_avatars.json`, `logs/` or local secrets. Git via PowerShell is safer for maintaining updates later.

## Security verification before pushing

```powershell
git status --ignored --short
git ls-files
```

Check that `.env`, private data, credentials, and logs do **not** appear in `git ls-files`. Remember that `.gitignore` does not untrack a file already committed; if a secret was committed, revoke it and clean up history using GitHub's official guidance.

## Documentation

- [Adding a locally hosted project to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
