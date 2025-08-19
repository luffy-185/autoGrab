import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# 🔹 Import keep_alive (Flask ping server)
try:
    from keep_alive import keep_alive
    KEEP_ALIVE_AVAILABLE = True
except ImportError:
    KEEP_ALIVE_AVAILABLE = False

# ================= CONFIG =================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

BOT_USERNAME = "Slave_waifu_bot"   # waifu bot username
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

MODE_DELAYS = {"bot": 2, "normal": 4, "human": 7}
CURRENT_MODE = "normal"

# DB FILES
DB1_FILE = "db1.json"  # main DB
DB2_FILE = "db2.json"  # new entries

# ================= GLOBAL STATE =================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

grab_enabled_chats = {}   # chat_id → bool
grab_all_enabled = False  # global toggle

# Load DBs
def load_db(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)
    with open(filename, "r") as f:
        return json.load(f)

def save_db(filename, db):
    with open(filename, "w") as f:
        json.dump(db, f, indent=2)

db1 = load_db(DB1_FILE)
db2 = load_db(DB2_FILE)

# ================= HELPERS =================
def extract_file_key(msg):
    if not msg.photo:
        return None
    return f"{msg.photo.id}_{msg.photo.access_hash}"

async def is_owner(event):
    return event.sender_id == OWNER_ID

# ================= GRABBING =================
@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def handler(event):
    global db1, db2

    chat_id = event.chat_id
    if not grab_all_enabled and not grab_enabled_chats.get(chat_id, False):
        return  # grabbing off for this chat

    if not event.photo:
        return  # must contain image

    key = extract_file_key(event)
    if not key:
        return

    delay = MODE_DELAYS.get(CURRENT_MODE, 3)
    await asyncio.sleep(delay)

    if key in db1:
        char_name = db1[key]
        await client.send_message(chat_id, f"/grab@{BOT_USERNAME} {char_name}")
    else:
        # store as unknown until user adds manually
        if key not in db2:
            db2[key] = "Unknown"
            save_db(DB2_FILE, db2)

# ================= COMMANDS =================
@client.on(events.NewMessage(pattern=r"^/grab (on|off)$"))
async def grab_toggle(event):
    if not await is_owner(event): return
    chat_id = event.chat_id
    state = event.pattern_match.group(1)
    grab_enabled_chats[chat_id] = (state == "on")
    await event.reply(f"✅ Auto-grab {'enabled' if state == 'on' else 'disabled'} for this chat")

@client.on(events.NewMessage(pattern=r"^/grab (onall|offall)$"))
async def grab_all_toggle(event):
    if not await is_owner(event): return
    global grab_all_enabled
    cmd = event.pattern_match.group(1)
    grab_all_enabled = (cmd == "onall")
    await event.reply(f"🌍 Auto-grab {'enabled' if grab_all_enabled else 'disabled'} globally")

@client.on(events.NewMessage(pattern=r"^/grab on (-?\d+)$"))
async def grab_specific(event):
    if not await is_owner(event): return
    chat_id = int(event.pattern_match.group(1))
    grab_enabled_chats[chat_id] = True
    await event.reply(f"✅ Auto-grab enabled for chat {chat_id}")

@client.on(events.NewMessage(pattern=r"^/addchar (.+)$"))
async def addchar(event):
    if not await is_owner(event): return
    if not event.is_reply:
        await event.reply("❌ Reply to the unknown character image to add.")
        return

    reply = await event.get_reply_message()
    key = extract_file_key(reply)
    if not key:
        await event.reply("❌ No image found.")
        return

    char_name = event.pattern_match.group(1).strip()
    db1[key] = char_name
    save_db(DB1_FILE, db1)

    if key in db2:
        del db2[key]
        save_db(DB2_FILE, db2)

    await event.reply(f"✅ Added `{char_name}` to DB1")

@client.on(events.NewMessage(pattern=r"^/status$"))
async def status(event):
    if not await is_owner(event): return
    msg = (
        "📊 Status:\n"
        f"- Global Grab: {grab_all_enabled}\n"
        f"- Chats Enabled: {len([c for c,v in grab_enabled_chats.items() if v])}\n"
        f"- Mode: {CURRENT_MODE} ({MODE_DELAYS[CURRENT_MODE]}s)\n"
        f"- DB1 Entries: {len(db1)}\n"
        f"- DB2 Entries: {len(db2)}\n"
    )
    await event.reply(msg)

@client.on(events.NewMessage(pattern=r"^/mode (.+)$"))
async def set_mode(event):
    if not await is_owner(event): return
    global CURRENT_MODE
    mode = event.pattern_match.group(1).lower()
    if mode in MODE_DELAYS:
        CURRENT_MODE = mode
        await event.reply(f"✅ Mode set to {CURRENT_MODE} ({MODE_DELAYS[CURRENT_MODE]}s)")
    else:
        await event.reply("❌ Invalid mode. Use: bot, normal, human")

# ================= MAIN =================
async def main():
    if KEEP_ALIVE_AVAILABLE:
        keep_alive()
    await client.start()
    print("✅ Bot started")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())












