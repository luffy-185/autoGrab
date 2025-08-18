import os
import json
import time
import asyncio
from typing import Dict, Tuple, Optional

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto
from aiohttp import web

# =========================
# ENV / CONFIG
# =========================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")  # <-- StringSession value
BOT_USERNAME = os.environ.get("BOT_USERNAME", "slave_waifu_bot")  # waifu bot username
DB_FILE = os.environ.get("DB_FILE", "db.json")  # your db.json (renamed ZDbx.json)
SPECIAL_CHAT = int(os.environ.get("SPECIAL_CHAT", "0"))  # chat ID for random messages

# Optional (nice to have). If set, only OWNER can run commands. If empty -> anyone can.
OWNER = os.environ.get("OWNER", "").lower()  # telegram username without @

# Optional custom random texts
RANDOM_MSG1_TEXT = os.environ.get("RANDOM_MSG1_TEXT", "🌸 Random message 1")
RANDOM_MSG2_TEXT = os.environ.get("RANDOM_MSG2_TEXT", "⚡ Random message 2")

# Validate critical env
if not (API_ID and API_HASH and SESSION_STRING):
    raise SystemExit("Missing API_ID, API_HASH, or SESSION_STRING env vars.")

# Load DB (read-only)
try:
    with open(DB_FILE, "r", encoding="utf-8") as f:
        DB: Dict[str, str] = json.load(f)
except Exception as e:
    raise SystemExit(f"Failed to load DB file '{DB_FILE}': {e}")

# =========================
# CLIENT
# =========================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# =========================
# STATE
# =========================
start_time = time.time()

# Autograb: global default + per-chat overrides
grabbing_global: bool = True  # /grabbing onall|offall toggles this
grabbing_overrides: Dict[int, bool] = {}  # chat_id -> True/False (overrides global)

# Random messages in SPECIAL_CHAT
randommsg_on: bool = False
randommsg_task: Optional[asyncio.Task] = None

# Per-chat spam: /spam <msg> <delay>   /spam off
spam_tasks: Dict[int, asyncio.Task] = {}                 # chat_id -> asyncio.Task
spam_settings: Dict[int, Tuple[str, int]] = {}           # chat_id -> (msg, delay)

# Counters (for status)
autograb_hits = 0
autograb_misses = 0
random_sent_1m = 0
random_sent_10m = 0
spam_sent_counts: Dict[int, int] = {}                    # chat_id -> count


# =========================
# HELPERS
# =========================
def uptime_hms() -> str:
    s = int(time.time() - start_time)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

async def is_owner(event) -> bool:
    if not OWNER:
        return True  # no restriction
    sender = await event.get_sender()
    return (sender.username or "").lower() == OWNER

def is_autograb_enabled(chat_id: int) -> bool:
    if chat_id in grabbing_overrides:
        return grabbing_overrides[chat_id]
    return grabbing_global


# =========================
# AUTOGRAB
# =========================
@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def autograb_handler(event):
    """Listens only to waifu bot messages, checks photo ID against DB, replies /grab or idk."""
    global autograb_hits, autograb_misses

    chat_id = event.chat_id
    if not is_autograb_enabled(chat_id):
        return

    # Only handle photo messages
    if not isinstance(event.media, MessageMediaPhoto):
        return

    try:
        photo = event.photo  # Telethon convenience attr
        if not photo:
            return
        file_key = f"{photo.id}_{photo.access_hash}"

        name = DB.get(file_key)
        if name:
            autograb_hits += 1
            await event.reply(f"/grab {name}")
        else:
            autograb_misses += 1
            await event.reply("idk")
    except Exception as e:
        # Don't crash on unexpected message shapes
        print("Autograb error:", e)


# =========================
# RANDOM MESSAGES (SPECIAL_CHAT)
# =========================
async def randommsg_loop():
    """Send two messages in SPECIAL_CHAT: one every 1m and one every 10m (interleaved)."""
    global random_sent_1m, random_sent_10m

    try:
        while randommsg_on and SPECIAL_CHAT != 0:
            # 1-minute message
            await client.send_message(SPECIAL_CHAT, RANDOM_MSG1_TEXT)
            random_sent_1m += 1
            for _ in range(60):
                if not randommsg_on: break
                await asyncio.sleep(1)
            if not randommsg_on: break

            # 10-minute message
            await client.send_message(SPECIAL_CHAT, RANDOM_MSG2_TEXT)
            random_sent_10m += 1
            for _ in range(600):
                if not randommsg_on: break
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print("Random loop error:", e)


# =========================
# SPAM (PER-CHAT)
# =========================
async def spam_loop(chat_id: int, msg: str, delay: int):
    """Send <msg> every <delay> seconds in the chat where command was issued."""
    try:
        while True:
            await client.send_message(chat_id, msg)
            spam_sent_counts[chat_id] = spam_sent_counts.get(chat_id, 0) + 1
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Spam loop error (chat {chat_id}):", e)


# =========================
# COMMANDS
# =========================

# /grabbing on | off | onall | offall
@client.on(events.NewMessage(pattern=r"^/grabbing(?:\s+(\w+))?$"))
async def grabbing_cmd(event):
    if not await is_owner(event):
        return
    chat_id = event.chat_id
    arg = (event.pattern_match.group(1) or "").lower()

    global grabbing_global

    if arg == "on":
        grabbing_overrides[chat_id] = True
        await event.reply("✅ Autograb ON in this chat.")
    elif arg == "off":
        grabbing_overrides[chat_id] = False
        await event.reply("❌ Autograb OFF in this chat.")
    elif arg == "onall":
        grabbing_global = True
        grabbing_overrides.clear()
        await event.reply("✅ Autograb ON for all chats (global).")
    elif arg == "offall":
        grabbing_global = False
        grabbing_overrides.clear()
        await event.reply("❌ Autograb OFF for all chats (global).")
    else:
        state = "ON" if is_autograb_enabled(chat_id) else "OFF"
        await event.reply(f"ℹ️ Autograb in this chat: {state} "
                          f"(global={'ON' if grabbing_global else 'OFF'})")

# /randommsg on | off
@client.on(events.NewMessage(pattern=r"^/randommsg(?:\s+(\w+))?$"))
async def randommsg_cmd(event):
    if not await is_owner(event):
        return
    global randommsg_on, randommsg_task

    arg = (event.pattern_match.group(1) or "").lower()

    if arg == "on":
        if SPECIAL_CHAT == 0:
            return await event.reply("⚠️ SPECIAL_CHAT not set. Set env var SPECIAL_CHAT.")
        if not randommsg_on:
            randommsg_on = True
            randommsg_task = asyncio.create_task(randommsg_loop())
        await event.reply(f"✅ Random messages ON in chat {SPECIAL_CHAT}.")
    elif arg == "off":
        randommsg_on = False
        if randommsg_task and not randommsg_task.done():
            randommsg_task.cancel()
        randommsg_task = None
        await event.reply("❌ Random messages OFF.")
    else:
        await event.reply("Usage: /randommsg on | off")

# /spam <msg> <delay>    OR    /spam off
@client.on(events.NewMessage(pattern=r"^/spam(?:\s+(.+))?$"))
async def spam_cmd(event):
    if not await is_owner(event):
        return
    chat_id = event.chat_id
    tail = (event.pattern_match.group(1) or "").strip()

    # off
    if tail.lower() == "off":
        task = spam_tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
        spam_tasks.pop(chat_id, None)
        spam_settings.pop(chat_id, None)
        await event.reply("🛑 Spam OFF in this chat.")
        return

    # parse "<msg> <delay>"
    if not tail:
        return await event.reply("Usage: /spam <message> <delaySec>  |  /spam off")

    parts = tail.rsplit(" ", 1)
    if len(parts) != 2:
        return await event.reply("⚠️ Provide both message and delay. Example: /spam hi 10")
    msg, delay_str = parts[0], parts[1]
    try:
        delay = int(delay_str)
        if delay < 1:
            raise ValueError
    except ValueError:
        return await event.reply("⚠️ Delay must be a positive integer (seconds).")

    # restart loop for this chat
    old = spam_tasks.get(chat_id)
    if old and not old.done():
        old.cancel()

    spam_settings[chat_id] = (msg, delay)
    spam_tasks[chat_id] = asyncio.create_task(spam_loop(chat_id, msg, delay))
    await event.reply(f"✅ Spamming in this chat.\n• Msg: {msg}\n• Delay: {delay}s")

# /status
@client.on(events.NewMessage(pattern=r"^/status$"))
async def status_cmd(event):
    if not await is_owner(event):
        return
    chat_id = event.chat_id

    ag_here = "ON" if is_autograb_enabled(chat_id) else "OFF"
    ag_global = "ON" if grabbing_global else "OFF"
    rm = "ON" if randommsg_on else "OFF"
    sp = "OFF"
    if chat_id in spam_settings:
        m, d = spam_settings[chat_id]
        sp = f"ON (msg='{m}', delay={d}s, sent={spam_sent_counts.get(chat_id, 0)})"

    msg = (
        "📊 **STATUS**\n"
        f"• Uptime: {uptime_hms()}\n"
        f"• Autograb (this chat): {ag_here}\n"
        f"• Autograb (global): {ag_global}\n"
        f"• RandomMsg (special {SPECIAL_CHAT}): {rm} | 1m sent: {random_sent_1m} | 10m sent: {random_sent_10m}\n"
        f"• Spam (this chat): {sp}\n"
        f"• Autograb hits: {autograb_hits} | misses: {autograb_misses}\n"
    )
    await event.reply(msg)


# =========================
# KEEP-ALIVE WEB SERVER (Render)
# =========================
async def handle_health(request):
    return web.Response(text="OK")

async def start_keepalive():
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("Keep-alive server running on :8080")


# =========================
# STARTUP
# =========================
async def main():
    await client.start()
    print("✅ Telegram client started.")
    await start_keepalive()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())




