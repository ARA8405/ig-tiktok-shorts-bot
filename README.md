# Instagram / TikTok / YouTube Shorts Downloader Telegram Bot

Add this bot to a group chat. Whenever someone posts an Instagram, TikTok,
or YouTube Shorts link, the bot downloads the video and replies with the
mp4 directly in the chat.

Note: regular long-form `youtube.com/watch?v=...` links are intentionally
ignored — only `youtube.com/shorts/...` and short `youtu.be/...` links are
picked up, to keep the bot scoped to short-form content.

## 1. Create the bot with BotFather (skip if you already have a token)

1. Open a chat with **@BotFather** in Telegram.
2. Send `/newbot`, give it a name and a username (must end in `bot`).
3. BotFather gives you a token like `123456789:AAExampleToken...`. Save it.

## 2. Turn OFF privacy mode (required for groups)

By default, Telegram bots can only see messages that start with `/command`
or `@mention` the bot. To let it read plain links in a group, disable
privacy mode:

1. Message **@BotFather** → `/mybots` → select your bot → **Bot Settings**
   → **Group Privacy** → **Turn off**.
2. If the bot is already in a group, remove it and re-add it after
   changing this setting (Telegram only applies it to new group joins).

Alternative: make the bot a group **admin** — admins can always see all
messages regardless of privacy mode.

## 3. Configure

```bash
cd ig-tiktok-bot
cp .env.example .env
```

Edit `.env` and set `TELEGRAM_BOT_TOKEN` to your token. Leave the rest as
defaults unless you hit the caveats below.

## 4. Install prerequisites

This project runs the same way on **macOS** and **Windows** — only the
prerequisite install commands differ.

**macOS:**
```bash
brew install python ffmpeg
```

**Windows** (PowerShell, as Administrator — requires [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/), included by default on Windows 10/11):
```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
```
Close and reopen your terminal after installing so `python` and `ffmpeg`
are on PATH.

## 5. Run it

### Option A — plain Python (good for testing)

A launcher script is included for each OS — it creates the virtual
environment, installs dependencies, and starts the bot in one step.

**macOS / Linux:**
```bash
./run.sh
```

**Windows** (double-click, or run from Command Prompt / PowerShell):
```
run.bat
```

Leave that terminal window running. Add the bot to a group and post an
Instagram/TikTok link to test it.

### Option B — Docker (recommended, easier to keep running reliably, identical on both OSes)

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
for macOS or Windows, then from this folder:

```bash
docker compose up -d --build
```

This runs the bot in the background and restarts it automatically if it
crashes or your machine reboots (as long as Docker Desktop is running).
View logs with `docker compose logs -f`.

## 6. Keep it running 24/7

The bot only responds while its process is running and your computer is on
and awake — it doesn't work like a cloud service that's always "just
there." If you want true always-on uptime without keeping your own machine
on, skip to "Move to a VPS" below — the exact same Docker setup works
there unchanged.

**On macOS**, if you're fine with the Mac needing to stay on:

- Prevent sleep while plugged in: System Settings → Battery → Power
  Adapter → uncheck "Put hard disks/display to sleep", or run
  `caffeinate -s` in a terminal you leave open.
- Use `com.user.igtiktokbot.plist` (included in this project) to run the
  bot as a background service via `launchd`, so it starts automatically on
  login and restarts itself if it crashes:

  ```bash
  # Edit the plist first: replace /Users/YOURNAME/... with your real path
  cp com.user.igtiktokbot.plist ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/com.user.igtiktokbot.plist
  ```

  To stop it: `launchctl unload ~/Library/LaunchAgents/com.user.igtiktokbot.plist`

**On Windows**, if you're fine with the PC needing to stay on:

- Prevent sleep: Settings → System → Power & battery → set "Screen and
  sleep" to Never while plugged in.
- Auto-start on login + auto-restart on crash, via Task Scheduler:
  1. Open **Task Scheduler** → **Create Task** (not "Basic Task").
  2. **General** tab: name it `ig-tiktok-bot`; select "Run whether user is
     logged on or not."
  3. **Triggers** tab → New → "At log on."
  4. **Actions** tab → New → Program/script: full path to
     `run.bat` in this folder; "Start in" = this folder's full path.
  5. **Settings** tab → check "Restart the task if it fails," every 1
     minute, up to a high attempt count.
  6. Save (you'll be prompted for your Windows password).

**Move to a VPS** (works identically for either OS you built this on):
rent a cheap always-on box (DigitalOcean, Hetzner, etc. — $4-6/mo is
plenty), install Docker, copy this folder over, add your `.env`, and run
`docker compose up -d --build`.

## Known limitations

- **File size**: the standard Telegram Bot API caps uploads at 50MB. Most
  short-form Reels/TikToks fit fine; longer/higher-quality videos may not.
  If a video is too large, the bot tells the group instead of failing
  silently. To raise this limit to 2GB, run a
  [local Bot API server](https://github.com/tdlib/telegram-bot-api) and
  point `python-telegram-bot` at it (more setup — ask if you want this).
- **Instagram rate limiting**: Instagram sometimes blocks anonymous
  requests. If downloads start failing, export your browser cookies for
  instagram.com to a `cookies.txt` file (e.g. with the "Get cookies.txt"
  browser extension) and set `COOKIES_FILE=cookies.txt` in `.env`.
- **Private content**: the bot can only download what's publicly
  accessible (or accessible via the cookies you provide) — private
  accounts/posts won't work unless the cookie account has access.
- **Platform changes**: Instagram/TikTok periodically change their sites,
  which can break extraction until `yt-dlp` is updated. Run
  `pip install -U yt-dlp` (or `docker compose build --no-cache`) if
  downloads suddenly stop working.
- Respect creators' rights and each platform's Terms of Service — this is
  meant for personal/fair use (e.g. saving your own posts or sharing with
  friends), not redistribution of others' content at scale.
