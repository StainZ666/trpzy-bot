import os
import re
import json
import math
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest

# ================= ENV CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty (set Environment Variable)")

# ================= BOT CONFIG =================
LOG_FOLDER = "logs"
DEFAULT_LIMIT = 500
MAX_LIMIT = 1000
THREADS = 6

START_IMAGE = os.getenv(
    "START_IMAGE",
    "https://i.ibb.co.com/1tm2gWPL/IMG-20260131-191235-274.jpg"
)

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "index.json")
os.makedirs(CACHE_DIR, exist_ok=True)

# ================= REGEX =================
REGEX_UP = re.compile(r"^[^:/\s]+:[^:/\s]+$")              # user:pass
REGEX_URLUP = re.compile(r"^https?://\S+:[^:\s]+:[^:\s]+$") # url:user:pass

user_session = {}

# ================= UTILS =================
def is_owner(update: Update):
    return update.effective_user and update.effective_user.id == OWNER_ID

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except:
        pass

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search UP", callback_data="mode_up"),
            InlineKeyboardButton("🌐 Search URLUP", callback_data="mode_urlup")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ])

def list_log_files():
    files = []
    for root, _, names in os.walk(LOG_FOLDER):
        for n in names:
            if n.endswith(".txt"):
                files.append(os.path.join(root, n))
    return files

# ================= SCANNER =================
def extract_up(line: str):
    """
    Return user:pass ONLY.
    Accepts:
      - user:pass
      - url:user:pass -> user:pass
    """
    line = line.strip()
    if ":" not in line:
        return None

    parts = line.split(":")
    if line.startswith("http") and len(parts) >= 3:
        up = parts[-2] + ":" + parts[-1]
        return up if REGEX_UP.fullmatch(up) else None

    return line if REGEX_UP.fullmatch(line) else None

def scan_file(path, keyword, mode, limit, cache):
    found = set()
    kw = keyword.lower()

    try:
        stat = os.stat(path)
        size = stat.st_size
        mtime = int(stat.st_mtime)
    except:
        return found

    cache.setdefault(kw, {})
    entry = cache[kw].get(path)

    try:
        with open(path, "r", errors="ignore") as f:
            # ===== CACHE FAST PATH =====
            if entry and entry.get("size") == size and entry.get("mtime") == mtime:
                for idx, line in enumerate(f):
                    if idx not in entry.get("lines", []):
                        continue
                    if len(found) >= limit:
                        break

                    line = line.strip()
                    if mode == "up":
                        up = extract_up(line)
                        if up:
                            found.add(up)
                    else:
                        if REGEX_URLUP.fullmatch(line):
                            found.add(line)
                return found

            # ===== FULL SCAN =====
            hit_lines = []
            for idx, line in enumerate(f):
                if len(found) >= limit:
                    break

                line = line.strip()
                if not line or kw not in line.lower():
                    continue

                hit_lines.append(idx)

                if mode == "up":
                    up = extract_up(line)
                    if up:
                        found.add(up)
                else:
                    if REGEX_URLUP.fullmatch(line):
                        found.add(line)

            cache[kw][path] = {
                "size": size,
                "mtime": mtime,
                "lines": hit_lines
            }

    except:
        pass

    return found

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    caption = (
        "🤖 *TrpZy Private Log Search Bot*\n\n"
        "⚡ Ultra Fast • MultiThread\n"
        "🧠 Smart Cache\n"
        "🧹 Clean Duplicate\n"
        "🔒 Private Only\n\n"
        "👇 Pilih mode"
    )

    await update.message.reply_photo(
        photo=START_IMAGE,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        user_session.pop(q.from_user.id, None)
        await q.edit_message_caption("❌ Dibatalkan")
        return

    mode = "up" if q.data == "mode_up" else "urlup"
    user_session[q.from_user.id] = mode

    await q.edit_message_caption(
        caption=f"📄 Mode: `{mode}`\n\nKirim *keyword* 🔎",
        parse_mode="Markdown"
    )

async def handle_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    uid = update.effective_user.id
    if uid not in user_session:
        return

    keyword = update.message.text.strip()
    mode = user_session.pop(uid)
    limit = DEFAULT_LIMIT

    files = list_log_files()
    total = len(files)

    progress = await update.message.reply_text(
        f"🔍 Keyword: `{keyword}`\n📂 Files: `{total}`\n⏳ Scanning...",
        parse_mode="Markdown"
    )

    cache = load_cache()
    results = set()
    done = 0
    last = time.time()

    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        futures = {
            ex.submit(scan_file, p, keyword, mode, limit, cache): p
            for p in files
        }

        for fut in as_completed(futures):
            done += 1
            results |= fut.result()
            if len(results) > limit:
                results = set(list(results)[:limit])

            if time.time() - last >= 1:
                percent = math.floor((done / max(total,1)) * 100)
                try:
                    await progress.edit_text(
                        f"📊 Progress: `{percent}%` ({done}/{total})\n"
                        f"📌 Result: `{len(results)}`",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                last = time.time()

            if len(results) >= limit:
                break

    save_cache(cache)

    if not results:
        await progress.edit_text("❌ Tidak ada hasil")
        return

    now = datetime.now()
    fname = f"TrpZy{keyword}_{now.day:02d}_{now.month:02d}_{now.year}.txt"

    with open(fname, "w") as f:
        f.write("\n".join(sorted(results)))

    await update.message.reply_document(
        open(fname, "rb"),
        caption=f"✅ *TrpZy Result* — {len(results)} line",
        parse_mode="Markdown"
    )

    os.remove(fname)

    await update.message.reply_text(
        "🔁 Search lagi?",
        reply_markup=main_keyboard()
    )

# ================= APP =================
request = HTTPXRequest(
    connect_timeout=20,
    read_timeout=20,
    write_timeout=20,
    pool_timeout=20
)

app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .request(request)
    .build()
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword))

print("🤖 TrpZy Bot RUNNING")
app.run_polling()
