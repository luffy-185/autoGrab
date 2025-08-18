import os, json, asyncio
from keep_alive import keep_alive
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto

keep_alive()

# ==== CONFIG ====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
OWNER_ID = int(os.getenv("OWNER"))  # Your Telegram ID
DB_FILE = "db.json"
SPECIAL_CHAT = int(os.getenv("SPECIAL_CHAT", 0))  # chat for random msgs
WAIFU_BOT_ID = int(os.getenv("BOT", 0))  # bot id for autograb
GRAB_KEYWORD = "ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀꜱ ᴀᴘᴘᴇᴀʀᴇᴅ!"

# ==== LOAD DB ====
if not os.path.exists(DB_FILE):
    DB = {}
else:
    with open(DB_FILE, "r", encoding="utf-8") as f:
        DB = json.load(f)

# ==== STATES ====
chat_states = {}  # {chat_id: {"grab": True, "spam": False}}
grab_global = True
spam_tasks = {}
random_tasks = {"1m": None, "10m": None}
random_state = {"1m": False, "10m": False}

# ==== FIXED RANDOM MESSAGES ====
random_msgs = {
    "1m": ["/EXPLORE", "/EXPLORE"],  # 1-minute interval message
    "10m": ["/PROPOSE", "/PROPOSE"]   # 10-minute interval message
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

# ==== AUTOGRAB ====
@client.on(events.NewMessage())
async def handler(event):
    if not is_grab_on(event.chat_id):
        return
    if WAIFU_BOT_ID and event.sender_id != WAIFU_BOT_ID:
        return
    if not event.message or not event.media:
        return
    if not isinstance(event.media, MessageMediaPhoto):
        return
    if GRAB_KEYWORD.lower() not in (event.message.message or "").lower():
        return
    if not hasattr(event.media, 'photo'):
        return

    stable_id = f"{event.media.photo.id}_{event.media.photo.access_hash}"
    if stable_id in DB:
        await event.reply(f"/grab {DB[stable_id]}")

# ==== SPAM ====
async def spam_loop(chat_id, msg, delay):
    while chat_states.get(chat_id, {}).get("spam", False):
        await client.send_message(chat_id, msg)
        await asyncio.sleep(delay)

@client.on(events.NewMessage(pattern=r"^/spam (.+) (\d+)$"))
@owner_only
async def start_spam(event):
    chat_id = event.chat_id
    msg, delay = event.pattern_match.groups()
    delay = int(delay)
    chat_states.setdefault(chat_id, {})["spam"] = True
    if chat_id in spam_tasks:
        try: spam_tasks[chat_id].cancel()
        except: pass
    spam_tasks[chat_id] = asyncio.create_task(spam_loop(chat_id, msg, delay))
    await event.reply(f"✅ Spamming `{msg}` every {delay}s")

@client.on(events.NewMessage(pattern=r"^/spam off$"))
@owner_only
async def stop_spam(event):
    chat_id = event.chat_id
    chat_states.setdefault(chat_id, {})["spam"] = False
    if chat_id in spam_tasks:
        try: spam_tasks[chat_id].cancel()
        except: pass
        del spam_tasks[chat_id]
    await event.reply("🛑 Spam stopped")

# ==== RANDOM MESSAGES ====
async def random_loop(chat_id, delay, key):
    msgs = random_msgs[key]
    i = 0
    while random_state[key]:
        await client.send_message(chat_id, msgs[i % len(msgs)])
        i += 1
        await asyncio.sleep(delay)

@client.on(events.NewMessage(pattern=r"^/random1 on$"))
@owner_only
async def random1_on(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["1m"] = True
    if random_tasks["1m"]:
        try: random_tasks["1m"].cancel()
        except: pass
    random_tasks["1m"] = asyncio.create_task(random_loop(event.chat_id, 66, "1m"))
    await event.reply("✅ Random1 ON (1m)")

@client.on(events.NewMessage(pattern=r"^/random1 off$"))
@owner_only
async def random1_off(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["1m"] = False
    if random_tasks["1m"]:
        try: random_tasks["1m"].cancel()
        except: pass
    await event.reply("🛑 Random1 OFF")

@client.on(events.NewMessage(pattern=r"^/random2 on$"))
@owner_only
async def random2_on(event):
    if event.chat_id != SPECIAL_CHAT:
        return
    random_state["10m"] = True
    if random_tasks["10m"]:
        try: random_tasks["10m"].cancel()
        except: pass
    random_tasks["10m"] = asyncio.create_task(random_loop(event.chat_id, 620, "10m"))
    await event.reply("✅ Random2 ON (10m)")

@client.on(events.NewMessage(pattern=r"^/random2 off$"))
@owner_only
async def random2_off(event):
    if event.chat_id != SPECIAL_CHAT:
        return
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

# ==== STATUS ====
@client.on(events.NewMessage(pattern=r"^/status$"))
@owner_only
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








