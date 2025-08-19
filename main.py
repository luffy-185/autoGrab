import asyncio, json, os, re
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from keep_alive import keep_alive

# ---------------- Config from Render ----------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION = os.getenv("SESSION_STRING", "session")
OWNER = os.getenv("OWNER_ID", "").lower()
DEFAULT_GROUP = os.getenv("DEFAULT_GROUP", "@noob_grabber")
CURRENT_SENDER = os.getenv("CURRENT_SENDER", "slave_waifu_bot")

DB1_PATH = "db1.json"
DB2_PATH = "db2.json"

CURRENT_DB = 1
CURRENT_MODE = "normal"
MODE_DELAYS = {"bot": 1, "normal": 2, "human": 3}

# ---------------- Logger ----------------
def log(msg):
    print(msg, flush=True)

# ---------------- Database ----------------
def load_db(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

db1 = db1.json
db2 = db2.json
current_db = db1 if CURRENT_DB == 1 else db2

# ---------------- Helpers ----------------
OWNER_ID = None

async def is_owner(event):
    global OWNER_ID
    sender = await event.get_sender()
    if not sender:
        return False
    if sender.username and sender.username.lower() == OWNER:
        OWNER_ID = sender.id
        return True
    if OWNER_ID and sender.id == OWNER_ID:
        return True
    return False

def extract_file_key(msg):
    if msg.media:
        if isinstance(msg.media, MessageMediaPhoto):
            return f"{msg.media.photo.id}_{msg.media.photo.access_hash}"
        if isinstance(msg.media, MessageMediaDocument):
            return f"{msg.media.document.id}_{msg.media.document.access_hash}"
    return None

def shortest_word(name):
    words = re.split(r"\s+", name.lower())
    words = [w for w in words if len(w) > 2]
    return min(words, key=len) if words else None

# ---------------- Client ----------------
client = TelegramClient(SESSION, API_ID, API_HASH)

@client.on(events.NewMessage)
async def auto_grabber(event):
    global current_db, CURRENT_SENDER
    chat = await event.get_chat()
    uname = getattr(chat, "username", None)
    if not uname or f"@{uname.lower()}" != DEFAULT_GROUP.lower():
        return

    # check sender
    sender = await event.get_sender()
    if not sender or not sender.username or sender.username.lower() != CURRENT_SENDER.lower():
        return

    text = event.raw_text or ""
    if "✨ ᴇɴɢᴀɢᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ʟᴜᴄᴋ ᴇᴠᴇɴᴛ ᴀᴄᴛɪᴠᴀᴛᴇᴅ! ✨" in text:
        key = extract_file_key(event.message)
        if key and key in current_db:
            char_name = current_db[key]
            grab_word = shortest_word(char_name)
            if grab_word:
                delay = MODE_DELAYS.get(CURRENT_MODE, 2)
                await asyncio.sleep(delay)
                await client.send_message(event.chat_id, f"/grab@Slave_waifu_bot {grab_word}")
                log(f"Grabbed {char_name} -> {grab_word}")
        else:
            log("Character not in DB, skipping")

# ---------------- Commands ----------------
@client.on(events.NewMessage(pattern=r"^/monitor"))
async def monitor_cmd(event):
    if not await is_owner(event): return
    global DEFAULT_GROUP
    parts = event.raw_text.split()
    if len(parts) > 1:
        DEFAULT_GROUP = parts[1]
        await event.reply(f"✅ Now monitoring {DEFAULT_GROUP}")
    else:
        await event.reply(f"📊 Monitoring {DEFAULT_GROUP}")

@client.on(events.NewMessage(pattern=r"^/sender"))
async def sender_cmd(event):
    if not await is_owner(event): return
    global CURRENT_SENDER
    parts = event.raw_text.split()
    if len(parts) > 1:
        CURRENT_SENDER = parts[1].lstrip("@")
        await event.reply(f"✅ Now only reacting to messages from @{CURRENT_SENDER}")
    else:
        await event.reply(f"📊 Current sender: @{CURRENT_SENDER}")

@client.on(events.NewMessage(pattern=r"^/usedb"))
async def usedb_cmd(event):
    if not await is_owner(event): return
    global CURRENT_DB, current_db
    parts = event.raw_text.split()
    if len(parts) > 1 and parts[1] in ["1","2"]:
        CURRENT_DB = int(parts[1])
        current_db = db1 if CURRENT_DB == 1 else db2
        await event.reply(f"✅ Using DB{CURRENT_DB}")
    else:
        await event.reply(f"📊 Current DB: {CURRENT_DB}")

@client.on(events.NewMessage(pattern=r"^/mode"))
async def mode_cmd(event):
    if not await is_owner(event): return
    global CURRENT_MODE
    parts = event.raw_text.split()
    if len(parts) > 1 and parts[1].lower() in MODE_DELAYS:
        CURRENT_MODE = parts[1].lower()
        await event.reply(f"✅ Mode set to {CURRENT_MODE} ({MODE_DELAYS[CURRENT_MODE]}s)")
    else:
        await event.reply(f"📊 Current mode: {CURRENT_MODE} ({MODE_DELAYS[CURRENT_MODE]}s)")

@client.on(events.NewMessage(pattern=r"^/name$"))
async def name_cmd(event):
    if not await is_owner(event): return
    if not event.is_reply:
        await event.reply("Reply to a message with /name")
        return
    reply = await event.get_reply_message()
    key = extract_file_key(reply)
    if key and key in current_db:
        await event.reply(f"Character: {current_db[key]}")
    else:
        await event.reply("❌ Not found in DB")

@client.on(events.NewMessage(pattern=r"^/status$"))
async def status_cmd(event):
    if not await is_owner(event): return
    msg = (
        f"📊 Status\n"
        f"- Monitoring: {DEFAULT_GROUP}\n"
        f"- Sender: @{CURRENT_SENDER}\n"
        f"- DB: {CURRENT_DB} (entries: {len(current_db)})\n"
        f"- Mode: {CURRENT_MODE} ({MODE_DELAYS[CURRENT_MODE]}s)\n"
    )
    await event.reply(msg)

@client.on(events.NewMessage(pattern=r"^/help$"))
async def help_cmd(event):
    if not await is_owner(event): return
    msg = (
        "🤖 Commands:\n"
        "/monitor <group>\n"
        "/sender <username>\n"
        "/usedb <1|2>\n"
        "/mode <bot|normal|human>\n"
        "/name (reply)\n"
        "/status\n"
        "/help\n"
    )
    await event.reply(msg)

# ---------------- Main ----------------
async def main():
    await client.start()
    log("Bot started ✅")
    await client.run_until_disconnected()

if __name__ == "__main__":
    keep_alive()
    client.loop.run_until_complete(main())












