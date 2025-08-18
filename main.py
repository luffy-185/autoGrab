import os, json, asyncio, random
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto

# ==== CONFIG ====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
DB_FILE = "db.json"
SPECIAL_CHAT = int(os.getenv("SPECIAL_CHAT", 0))  # random msg chat

# Keyword that must appear in bot msgk'[p
GRAB_KEYWORD = "ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀꜱ ᴀᴘᴘᴇᴀʀᴇᴅ!"  # EDIT THIS

# Load DB
with open(DB_FILE, "r", encoding="utf-8") as f:
    DB = json.load(f)

# Feature states
chat_states = {}   # {chat_id: {"grab": True, "spam": False}}
grab_global = True
spam_tasks = {}
random_tasks = {"1m": None, "10m": None}
random_state = {"1m": False, "10m": False}

RANDOM_MSGS = ["Hello!", "Ping!", "I'm alive!", "😎", "💀"]

# === CLIENT ===
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

def is_grab_on(chat_id):
    if not grab_global:
        return False
    return chat_states.get(chat_id, {}).get("grab", False)

# ==== AUTOGRAB ====
@client.on(events.NewMessage())
async def handler(event):
    chat_id = event.chat_id
    if not is_grab_on(chat_id):
        return
    if not event.message or not event.media:
        return
    if not isinstance(event.media, MessageMediaPhoto):
        return
    if GRAB_KEYWORD.lower() not in (event.message.message or "").lower():
        return

    stable_id = f"{event.photo.id}_{event.photo.access_hash}"
    if stable_id in DB:
        await event.reply(f"/grab {DB[stable_id]}")

# ==== AUTOSPAM ====
async def spam_loop(chat_id, msg, delay):
    while chat_states.get(chat_id, {}).get("spam", False):
        await client.send_message(chat_id, msg)
        await asyncio.sleep(delay)

@client.on(events.NewMessage(pattern=r"^/spam (.+) (\d+)$"))
async def start_spam(event):
    chat_id = event.chat_id
    msg, delay = event.pattern_match.groups()
    delay = int(delay)
    chat_states.setdefault(chat_id, {})["spam"] = True
    if chat_id in spam_tasks:
        spam_tasks[chat_id].cancel()
    spam_tasks[chat_id] = asyncio.create_task(spam_loop(chat_id, msg, delay))
    await event.reply(f"✅ Spamming `{msg}` every {delay}s")

@client.on(events.NewMessage(pattern=r"^/spam off$"))
async def stop_spam(event):
    chat_id = event.chat_id
    chat_states.setdefault(chat_id, {})["spam"] = False
    if chat_id in spam_tasks:
        spam_tasks[chat_id].cancel()
        del spam_tasks[chat_id]
    await event.reply("🛑 Spam stopped")

# ==== RANDOM MESSAGES ====
async def random_loop(chat_id, delay, key):
    while random_state[key]:
        msg = random.choice(RANDOM_MSGS)
        await client.send_message(chat_id, msg)
        await asyncio.sleep(delay)

@client.on(events.NewMessage(pattern=r"^/random1 on$"))
async def random1_on(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["1m"] = True
    if random_tasks["1m"]:
        random_tasks["1m"].cancel()
    random_tasks["1m"] = asyncio.create_task(random_loop(event.chat_id, 60, "1m"))
    await event.reply("✅ Random1 ON (1m)")

@client.on(events.NewMessage(pattern=r"^/random1 off$"))
async def random1_off(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["1m"] = False
    if random_tasks["1m"]:
        random_tasks["1m"].cancel()
    await event.reply("🛑 Random1 OFF")

@client.on(events.NewMessage(pattern=r"^/random2 on$"))
async def random2_on(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["10m"] = True
    if random_tasks["10m"]:
        random_tasks["10m"].cancel()
    random_tasks["10m"] = asyncio.create_task(random_loop(event.chat_id, 600, "10m"))
    await event.reply("✅ Random2 ON (10m)")

@client.on(events.NewMessage(pattern=r"^/random2 off$"))
async def random2_off(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["10m"] = False
    if random_tasks["10m"]:
        random_tasks["10m"].cancel()
    await event.reply("🛑 Random2 OFF")

# ==== GRAB ON/OFF ====
@client.on(events.NewMessage(pattern=r"^/grab on$"))
async def grab_on(event):
    chat_states.setdefault(event.chat_id, {})["grab"] = True
    await event.reply("✅ Grab ON (this chat)")

@client.on(events.NewMessage(pattern=r"^/grab off$"))
async def grab_off(event):
    chat_states.setdefault(event.chat_id, {})["grab"] = False
    await event.reply("🛑 Grab OFF (this chat)")

@client.on(events.NewMessage(pattern=r"^/grab onall$"))
async def grab_onall(event):
    global grab_global
    grab_global = True
    await event.reply("🌍 Grab ON (all chats)")

@client.on(events.NewMessage(pattern=r"^/grab offall$"))
async def grab_offall(event):
    global grab_global
    grab_global = False
    await event.reply("🌍 Grab OFF (all chats)")

# ==== STATUS ====
@client.on(events.NewMessage(pattern=r"^/status$"))
async def status(event):
    st = chat_states.get(event.chat_id, {})
    msg = f"""📊 Status:
Grab Global: {"✅" if grab_global else "❌"}
Grab Here: {"✅" if st.get("grab", False) else "❌"}
Spam: {"✅" if st.get("spam", False) else "❌"}
Random1: {"✅" if random_state["1m"] else "❌"}
Random2: {"✅" if random_state["10m"] else "❌"}
"""
    await event.reply(msg)

# ==== START ====
print("🚀 Bot starting...")
client.start()
client.run_until_disconnected()






