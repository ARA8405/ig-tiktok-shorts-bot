#!/usr/bin/env python3
"""
Telegram bot that watches group chats for Instagram / TikTok / YouTube
Shorts links and replies with the downloaded video (mp4).

Add the bot to a group, make sure privacy mode is OFF (see README), and
send a link -- the bot downloads it with yt-dlp and uploads the mp4.
"""

import asyncio
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)
import yt_dlp

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
COOKIES_FILE = os.getenv("COOKIES_FILE", "").strip() or None
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
ALLOWED_CHAT_IDS_RAW = os.getenv("ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHAT_IDS = (
    {int(x) for x in ALLOWED_CHAT_IDS_RAW.split(",") if x.strip()}
    if ALLOWED_CHAT_IDS_RAW
    else None
)

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("ig-tiktok-bot")

# Matches Instagram (posts/reels/tv), TikTok (incl. short vm./vt. links),
# and YouTube Shorts (both youtube.com/shorts/... and youtu.be/... short
# links). Regular long-form youtube.com/watch links are intentionally NOT
# matched, to keep this bot scoped to short-form content.
URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.|vm\.|vt\.)?(?:instagram\.com|tiktok\.com)/\S+"
    r"|https?://(?:www\.|m\.)?youtube\.com/shorts/\S+"
    r"|https?://youtu\.be/\S+",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    if not text:
        return []
    # Trim common trailing punctuation Telegram/users leave attached to links
    return [u.rstrip(").,!?\"'") for u in URL_PATTERN.findall(text)]


@dataclass
class Downloaded:
    path: Path
    request_dir: Path
    width: int | None
    height: int | None
    duration: int | None


def download_video(url: str, out_dir: Path) -> Downloaded:
    """Blocking download via yt-dlp. Runs in a thread executor.

    Each call gets its own fresh, uniquely-named subdirectory so there is
    no possibility of picking up a leftover file from a previous request.
    """
    request_dir = out_dir / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=False)
    out_template = str(request_dir / "video.%(ext)s")

    ydl_opts = {
        "outtmpl": out_template,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024 * 2,  # soft cap, checked again after
        "socket_timeout": 30,
        "retries": 3,
        "cachedir": False,  # don't let yt-dlp's extractor cache affect results
        # YouTube's "web" client frequently returns download URLs that come
        # back as HTTP 403. The android/ios clients are far less prone to
        # this. Harmless no-op for Instagram/TikTok URLs.
        "extractor_args": {
            "youtube": {"player_client": ["android", "ios", "web"]}
        },
    }
    if COOKIES_FILE:
        ydl_opts["cookiefile"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    path = Path(filename)
    # yt-dlp may have merged to .mp4 with a different final extension
    if not path.exists():
        mp4_candidate = path.with_suffix(".mp4")
        if mp4_candidate.exists():
            path = mp4_candidate
        else:
            matches = [p for p in request_dir.glob("video.*") if p.is_file()]
            if matches:
                path = matches[0]
            else:
                raise FileNotFoundError("yt-dlp reported success but no output file was found")

    return Downloaded(
        path=path,
        request_dir=request_dir,
        width=info.get("width"),
        height=info.get("height"),
        duration=int(info["duration"]) if info.get("duration") else None,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return

    if ALLOWED_CHAT_IDS and update.effective_chat.id not in ALLOWED_CHAT_IDS:
        return

    urls = extract_urls(message.text)
    if not urls:
        return

    for url in urls:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO
        )
        status_msg = await message.reply_text(
            "Downloading...", reply_to_message_id=message.message_id
        )

        downloaded: Downloaded | None = None
        try:
            loop = asyncio.get_running_loop()
            downloaded = await loop.run_in_executor(None, download_video, url, DOWNLOAD_DIR)
            video_path = downloaded.path

            size_mb = video_path.stat().st_size / (1024 * 1024)
            log.info(
                "Downloaded %s -> %s (%.1fMB, %sx%s, %ss)",
                url,
                video_path,
                size_mb,
                downloaded.width,
                downloaded.height,
                downloaded.duration,
            )
            if size_mb > MAX_FILE_SIZE_MB:
                await status_msg.edit_text(
                    f"That video is {size_mb:.1f}MB, which is over the "
                    f"{MAX_FILE_SIZE_MB}MB limit for this bot. Skipping upload.\n"
                    f"(See README for how to raise this limit with a local Bot API server.)"
                )
                continue

            with open(video_path, "rb") as f:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=InputFile(f, filename="video.mp4"),
                    caption=None,
                    width=downloaded.width,
                    height=downloaded.height,
                    duration=downloaded.duration,
                    supports_streaming=True,
                    reply_to_message_id=message.message_id,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
            await status_msg.delete()

        except yt_dlp.utils.DownloadError as e:
            log.warning("Download failed for %s: %s", url, e)
            await status_msg.edit_text(
                "Couldn't download that video (it may be private, age-restricted, "
                "or the link is invalid)."
            )
        except Exception:
            log.exception("Unexpected error handling %s", url)
            await status_msg.edit_text("Something went wrong downloading that video.")
        finally:
            if downloaded is not None and downloaded.request_dir.exists():
                shutil.rmtree(downloaded.request_dir, ignore_errors=True)


async def on_startup(application: Application) -> None:
    me = await application.bot.get_me()
    log.info("Bot started as @%s", me.username)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    # On newer Python versions (3.12+) there is no implicit event loop on the
    # main thread anymore, which makes some python-telegram-bot internals
    # (run_polling's asyncio.get_event_loop() call) raise RuntimeError.
    # Explicitly creating and setting one here keeps this working regardless
    # of Python version.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    application = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    log.info("Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()