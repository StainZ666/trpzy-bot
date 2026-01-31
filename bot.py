# ============================
# 🤖 TrpZy Private Search Bot
# ============================

import os
import re
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

LOG_DIR = "logs"
RESULT_DIR = "results"
CACHE_DIR = "cache"

DEFAULT_LIMIT = 500
MAX_LIMIT = 1000
THREADS = 16

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ========= REGEX =========
REGEX_URL = re.compile(r"https?://[^\s:/]+[:/]+([^:\s]+):([^:\s]+)")
REGEX_UP = re.compile(r"^([^:\s]+):([^:\s]+)$")

# ========= UTIL =========
def banner():
    return """
🤖 TrpZy Bot RUNNING
Ultra Fast • MultiThread
Private Access Only
"""

def extract_user_pass(line: str):
    line = line.strip()
    m = REGEX_URL.search(line)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    m = REGEX_UP.match(line)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    return None

def scan_file(path, keyword):
    results = set()
    try:
        with open(path, "r", errors="ignore") as f:
            for line in f:
                if keyword.lower() in line.lower():
                    up = extract_user_pass(line)
                    if up:
                        results.add(up)
    except:
        pass
    return results

def scan_all(keyword):
    all_results = set()
    files = [
        os.path.join(LOG_DIR, f)
        for f in os.listdir(LOG_DIR)
        if os.path.isfile(os.path.join(LOG_DIR, f))
    ]

    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        tasks = [ex.submit(scan_file, f, keyword) for f in files]
        for t in tasks:
            all_results.update(t.result())

    return all_results

# ========= BOT HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Private bot.")
        return

    await update.message.reply_photo(
        photo="https://i.ibb.co.com/1tm2gWPL/IMG-20260131-191235-274.jpg",
        caption=banner(),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔍 Search", callback_data="search")]]
        ),
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "search":
        await q.message.reply_text(
            "Gunakan:\n/search <keyword> [limit]\n\nContoh:\n/search roblox 500"
        )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text("❌ Keyword kosong.")
        return

    keyword = context.args[0]
    limit = DEFAULT_LIMIT

    if len(context.args) > 1:
        try:
            limit = min(int(context.args[1]), MAX_LIMIT)
        except:
            pass

    msg = await update.message.reply_text("⏳ Scanning logs...")

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, scan_all, keyword)

    if not results:
        await msg.edit_text("❌ Tidak ada hasil.")
        return

    results = list(results)[:limit]

    now = datetime.now()
    fname = f"TrpZy{keyword}_{now.day}_{now.month}_{now.year}.txt"
    fpath = os.path.join(RESULT_DIR, fname)

    with open(fpath, "w") as f:
        f.write("\n".join(results))

    await msg.edit_text(f"✅ Ditemukan {len(results)} result")
    await update.message.reply_document(InputFile(fpath))

# ========= MAIN =========
def main():
    print(banner())
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()

if __name__ == "__main__":
    main()
