import os
import html
import logging
from urllib.parse import quote_plus

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEZER_API = "https://api.deezer.com/search"
TIMEOUT = 12

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

WELCOME = (
    "سلام! 🎵 به موزیک‌یاب ایرانی خوش اومدی.\n\n"
    "یکی از این موارد رو بفرست:\n"
    "• اسم آهنگ\n"
    "• نام خواننده\n"
    "• یک جمله از متن ترانه\n\n"
    "برای نتیجه بهتر، اسم آهنگ یا خواننده رو دقیق بنویس.\n"
    "جست‌وجوی متن ترانه ممکنه نتیجه قطعی نده؛ در این حالت لینک جست‌وجوی وب هم نمایش داده می‌شه."
)

def deezer_search(query: str):
    """Search publicly available Deezer catalog metadata; no API key required."""
    try:
        response = requests.get(
            DEEZER_API,
            params={"q": query, "limit": 5},
            timeout=TIMEOUT,
            headers={"User-Agent": "IranMusicFinderBot/1.0"}
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", []) or []
    except Exception as exc:
        log.warning("Deezer search failed: %s", exc)
        return []

def safe_text(value):
    return html.escape(str(value or ""))

def result_text(track):
    title = safe_text(track.get("title", "نامشخص"))
    artist = safe_text((track.get("artist") or {}).get("name", "نامشخص"))
    album = safe_text((track.get("album") or {}).get("title", "نامشخص"))
    duration = int(track.get("duration") or 0)
    minutes, seconds = divmod(duration, 60)
    preview = track.get("preview")
    link = track.get("link")
    cover = (track.get("album") or {}).get("cover_medium")

    text = (
        f"🎵 <b>{title}</b>\n"
        f"🎤 خواننده: {artist}\n"
        f"💿 آلبوم: {album}\n"
        f"⏱ مدت: {minutes}:{seconds:02d}\n"
    )
    buttons = []
    if preview:
        buttons.append([InlineKeyboardButton("▶️ پخش پیش‌نمایش ۳۰ ثانیه‌ای", url=preview)])
    if link:
        buttons.append([InlineKeyboardButton("🎧 شنیدن در Deezer", url=link)])
    if cover:
        text += f"\n🖼️ کاور آلبوم در دسترس است."
    text += (
        "\n\nℹ️ پیش‌نمایش و لینک‌های رسمی برای شنیدن ارائه می‌شوند. "
        "این ربات لینک دانلود غیرمجاز آثار دارای حق نشر ارائه نمی‌کند."
    )
    return text, InlineKeyboardMarkup(buttons) if buttons else None, cover

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "راهنما 🎵\n"
        "اسم آهنگ یا خواننده را بفرست تا در فهرست موسیقی جست‌وجو کنم.\n"
        "اگر فقط بخشی از متن ترانه را داری، همان جمله را بفرست؛ "
        "در کنار نتایج احتمالی، لینک جست‌وجوی وب هم می‌دهم.\n\n"
        "توجه: جست‌وجوی متن ترانه تضمینی نیست و ممکن است لازم باشد چند عبارت مختلف را امتحان کنی."
    )

async def search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.message.text or "").strip()
    if not query:
        return
    if len(query) > 180:
        await update.message.reply_text("لطفاً عبارت کوتاه‌تری بفرست (حداکثر ۱۸۰ نویسه).")
        return

    await update.message.reply_text("🔎 دارم جست‌وجو می‌کنم، یک لحظه صبر کن…")
    tracks = deezer_search(query)

    if tracks:
        await update.message.reply_text(
            f"🎶 نتیجه‌های احتمالی برای: «{safe_text(query)}»",
            parse_mode=ParseMode.HTML
        )
        for track in tracks[:5]:
            text, keyboard, cover = result_text(track)
            try:
                if cover:
                    await update.message.reply_photo(
                        photo=cover, caption=text, reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await update.message.reply_text(
                        text, reply_markup=keyboard, parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
            except Exception:
                await update.message.reply_text(
                    text, reply_markup=keyboard, parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
    else:
        await update.message.reply_text(
            "در کاتالوگ موسیقی نتیجه‌ای پیدا نکردم. می‌تونی لینک‌های جست‌وجوی وب رو امتحان کنی."
        )

    # These search links are useful for lyric snippets, which Deezer's public search
    # endpoint does not reliably index as lyrics.
    encoded = quote_plus(query)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 جست‌وجوی عبارت در وب", url=f"https://www.google.com/search?q={encoded}+متن+آهنگ")],
        [InlineKeyboardButton("▶️ جست‌وجو در YouTube", url=f"https://www.youtube.com/results?search_query={encoded}+آهنگ")],
        [InlineKeyboardButton("🎵 جست‌وجو در Deezer", url=f"https://www.deezer.com/search/{encoded}")]
    ])
    await update.message.reply_text(
        "اگر عبارتت بخشی از متن ترانه است، این جست‌وجوها ممکنه کمک کنن آهنگ دقیق رو پیدا کنی:",
        reply_markup=keyboard
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

def main():
    if not BOT_TOKEN:
        raise RuntimeError("متغیر محیطی BOT_TOKEN تنظیم نشده است.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    log.info("Iran Music Finder bot is running")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
