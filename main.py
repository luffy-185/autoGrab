import os, json, asyncio, time, random
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto
from keep_alive import keep_alive

# ==== CONFIG ====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
OWNER_ID = int(os.getenv("OWNER_ID"))
DB_FILE = "db.json"
SPECIAL_CHAT = int(os.getenv("SPECIAL_CHAT", 0))  # chat for random msgs
WAIFU_BOT_ID = int(os.getenv("WAIFU_BOT_ID", 7438162678))
GRAB_KEYWORD = "/grab"

# ==== LOAD DB ====
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {DB_FILE} contains invalid JSON. Starting empty DB.")
        return {}

def save_db():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(DB, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving DB: {e}")
        return False

DB = load_db()

# ==== STATES ====
chat_states = {}  # {chat_id: {"grab": True, "spam": False}}
grab_global = True
spam_tasks = {}
random_tasks = {"1m": None, "10m": None}
random_state = {"1m": False, "10m": False}
bot_start_time = time.time()

# ==== RANDOM MESSAGES ====
RANDOM_MSGS = {
    "1m": ["/EXPLORE", "/EXPLORE"],
    "10m": ["/PROPOSE", "/PROPOSE"]
}

# ==== CLIENT ====
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# ==== OWNER ONLY DECORATOR ====
def owner_only(func):
    async def wrapper(event):
        if event.sender_id != OWNER_ID:
            return
        await func(event)
    return wrapper

def is_grab_on(chat_id):
    return grab_global and chat_states.get(chat_id, {}).get("grab", False)

# ==== UNIQUE IMAGE ID ====
def get_unique_image_id(photo):
    if hasattr(photo, 'file_reference') and photo.file_reference:
        return f"ref_{photo.file_reference.hex()}"
    elif hasattr(photo, 'id') and hasattr(photo, 'access_hash'):
        return f"{photo.id}_{photo.access_hash}"
    return str(getattr(photo, 'id', 'unknown'))

def find_character_by_id(image_id):
    if not image_id:
        return None
    if image_id in DB:
        return DB[image_id]
    for stored_id, char_name in DB.items():
        if '_' in image_id and '_' in stored_id:
            if image_id.split('_')[0] == stored_id.split('_')[0]:
                return char_name
    return None

# ==== AUTOGRAB ====
@client.on(events.NewMessage())
async def autograb_handler(event):
    if not event.message:
        return
    if not is_grab_on(event.chat_id):
        return
    if WAIFU_BOT_ID and event.sender_id != WAIFU_BOT_ID:
        return
    if not event.media or not isinstance(event.media, MessageMediaPhoto):
        return
    if GRAB_KEYWORD.lower() not in (event.message.message or "").lower():
        return

    photo = event.media.photo
    unique_id = get_unique_image_id(photo)
    char_name = find_character_by_id(unique_id)
    if char_name:
        try:
            await event.reply(f"/grab {char_name}")
        except: pass

# ==== ADD CHARACTER ====
@client.on(events.NewMessage(pattern=r"^/addchar (.+)$"))
@owner_only
async def add_character(event):
    char_name = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if not reply or not reply.media or not isinstance(reply.media, MessageMediaPhoto):
        await event.reply("❌ Reply to a message with an image to add character")
        return
    photo = reply.media.photo
    unique_id = get_unique_image_id(photo)
    DB[unique_id] = char_name
    if save_db():
        await event.reply(f"✅ Added {char_name} to database\nID: `{unique_id}`")
    else:
        await event.reply("❌ Error saving database")

# ==== STATUS ====
@client.on(events.NewMessage(pattern=r"^/status$"))
@owner_only
async def status(event):
    uptime_seconds = int(time.time() - bot_start_time)
    h, m, s = uptime_seconds // 3600, (uptime_seconds % 3600)//60, uptime_seconds % 60
    st = chat_states.get(event.chat_id, {})
    msg = f"""📊 Status:
⏰ Uptime: {h:02d}:{m:02d}:{s:02d}
🌍 Grab Global: {"✅" if grab_global else "❌"}
🎯 Grab Here: {"✅" if st.get("grab", False) else "❌"}
💬 Spam: {"✅" if st.get("spam", False) else "❌"}
🎲 Random1: {"✅" if random_state["1m"] else "❌"}
🎲 Random2: {"✅" if random_state["10m"] else "❌"}
📚 DB Entries: {len(DB)}
"""
    await event.reply(msg)

# ==== HELP ====
@client.on(events.NewMessage(pattern=r"^/help$"))
@owner_only
async def help_command(event):
    help_text = """🤖 Bot Commands:

**Autograb:**
/grab on/off - Toggle grab in this chat
/grab onall/offall - Toggle grab globally
/addchar Name - Reply to image to add character
/dbinfo - Show database info

**Spam:**
/spam message delay - Start spamming
/spam off - Stop spam

**Random (Special Chat Only):**
/random1 on/off - Toggle 1min messages
/random2 on/off - Toggle 10min messages

**Other:**
/status - Show bot status
/help - Show this message"""
    await event.reply(help_text)

# ==== SPAM ====
async def spam_loop(chat_id, msg, delay):
    while chat_states.get(chat_id, {}).get("spam", False):
        try:
            await client.send_message(chat_id, msg)
            await asyncio.sleep(delay)
        except:
            await asyncio.sleep(delay)

@client.on(events.NewMessage(pattern=r"^/spam (.+) (\d+)$"))
@owner_only
async def start_spam(event):
    msg, delay = event.pattern_match.groups()
    delay = int(delay)
    chat_states.setdefault(event.chat_id, {})["spam"] = True
    if event.chat_id in spam_tasks:
        spam_tasks[event.chat_id].cancel()
    spam_tasks[event.chat_id] = asyncio.create_task(spam_loop(event.chat_id, msg, delay))
    await event.reply(f"✅ Spamming `{msg}` every {delay}s")

@client.on(events.NewMessage(pattern=r"^/spam off$"))
@owner_only
async def stop_spam(event):
    chat_states.setdefault(event.chat_id, {})["spam"] = False
    if event.chat_id in spam_tasks:
        spam_tasks[event.chat_id].cancel()
        del spam_tasks[event.chat_id]
    await event.reply("🛑 Spam stopped")

# ==== RANDOM MESSAGES ====
async def random_loop(chat_id, delay, key):
    msgs = RANDOM_MSGS[key]
    i = 0
    while random_state[key]:
        try:
            await client.send_message(chat_id, msgs[i % len(msgs)])
            i += 1
            await asyncio.sleep(delay)
        except:
            await asyncio.sleep(delay)

@client.on(events.NewMessage(pattern=r"^/random1 on$"))
@owner_only
async def random1_on(event):
    if SPECIAL_CHAT == 0 or event.chat_id != SPECIAL_CHAT:
        await event.reply("❌ This command works only in special chat")
        return
    random_state["1m"] = True
    if random_tasks["1m"]:
        try: random_tasks["1m"].cancel()
        except: pass
    random_tasks["1m"] = asyncio.create_task(random_loop(event.chat_id, 68, "1m"))
    await event.reply("✅ Random1 ON (1 min)")

@client.on(events.NewMessage(pattern=r"^/random1 off$"))
@owner_only
async def random1_off(event):
    random_state["1m"] = False
    if random_tasks["1m"]:
        try: random_tasks["1m"].cancel()
        except: pass
    await event.reply("🛑 Random1 OFF")

@client.on(events.NewMessage(pattern=r"^/random2 on$"))
@owner_only
async def random2_on(event):
    if SPECIAL_CHAT == 0 or event.chat_id != SPECIAL_CHAT:
        await event.reply("❌ This command works only in special chat")
        return
    random_state["10m"] = True
    if random_tasks["10m"]:
        try: random_tasks["10m"].cancel()
        except: pass
    random_tasks["10m"] = asyncio.create_task(random_loop(event.chat_id, 620, "10m"))
    await event.reply("✅ Random2 ON (10 min)")

@client.on(events.NewMessage(pattern=r"^/random2 off$"))
@owner_only
async def random2_off(event):
    random_state["10m"] = False
    if random_tasks["10m"]:
        try: random_tasks["10m"].cancel()
        except: pass
    await event.reply("🛑 Random2 OFF")

# ==== GRAB ON/OFF ====
@client.on(events.NewMessage(pattern=r"^/grab on$"))
@owner_only
async def grab_on(event):
    chat_states.setdefault(event.chat_id, {})["grab"] = True
    await event.reply("✅ Grab ON (this chat)")

@client.on(events.NewMessage(pattern=r"^/grab off$"))
@owner_only
async def grab_off(event):
    chat_states.setdefault(event.chat_id, {})["grab"] = False
    await event.reply("🛑 Grab OFF (this chat)")

@client.on(events.NewMessage(pattern=r"^/grab onall$"))
@owner_only
async def grab_onall(event):
    global grab_global
    grab_global = True
    await event.reply("🌍 Grab ON (all chats)")

@client.on(events.NewMessage(pattern=r"^/grab offall$"))
@owner_only
async def grab_offall(event):
    global grab_global
    grab_global = False
    await event.reply("🌍 Grab OFF (all chats)")

# ==== MAIN ====
async def main():
    keep_alive()
    await client.start()
    print("🚀 Bot started and running")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())










