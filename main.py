import os, json, re, asyncio, time
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
  
# ===== CONFIG =====
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION = os.environ.get("SESSION")
DB_FILE = "db.json"   # GitHub JSON file cloned locally
SPECIAL_CHAT = int(os.environ.get("SPECIAL_CHAT"))  # GC for random msg

BOT_USERNAME = os.environ.get("BOT_USERNAME")  # waifu bot username/id

# ===== GLOBAL STATE =====
autograb_status = {}   # per chat on/off
autograb_global = False

random1_on = False
random10_on = False

spam_settings = {}   # {chat_id: {"msg": str, "delay": int, "task": asyncio.Task}}

START_TIME = time.time()

# Load DB
with open(DB_FILE, "r", encoding="utf-8") as f:
    DB = json.load(f)

# ===== CLIENT =====
client = TelegramClient(SESSION, API_ID, API_HASH)

# ===== CLEAN NAME MATCH =====
def clean_text(text):
    text = re.sub(r"[\[\]\(\)\{\}]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

def find_name(photo):
    file_id = f"{photo.id}_{photo.access_hash}"
    return DB.get(file_id)

# ===== AUTO GRAB =====
@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def autograb_handler(event):
    chat_id = event.chat_id
    if not (autograb_global or autograb_status.get(chat_id, False)):
        return

    if isinstance(event.media, MessageMediaPhoto):
        name = find_name(event.photo)
        if name:
            await event.reply(f"/grab {name}")
        else:
            await event.reply("idk")

# ===== COMMANDS =====
@client.on(events.NewMessage(pattern=r"^/(\w+)", func=lambda e: e.is_private or e.is_group))
async def command_handler(event):
    global autograb_global, random1_on, random10_on

    chat_id = event.chat_id
    cmd, *args = event.raw_text.split(maxsplit=1)
    cmd = cmd.lower()

    # --- AUTOGRAB ---
    if cmd == "/grabbing":
        if args and args[0].lower() == "on":
            autograb_status[chat_id] = True
            await event.reply("✅ Autograb ON for this chat")
        elif args and args[0].lower() == "off":
            autograb_status[chat_id] = False
            await event.reply("❌ Autograb OFF for this chat")

    elif cmd == "/onall":
        autograb_global = True
        await event.reply("🌍 Autograb ON for all chats")

    elif cmd == "/offall":
        autograb_global = False
        await event.reply("🌍 Autograb OFF for all chats")

    # --- RANDOM MSGS ---
    elif cmd == "/random1":
        if args and args[0].lower() == "on":
            random1_on = True
            await event.reply("/explore")
        elif args and args[0].lower() == "✅ RandomMsg (1m) ON":
            random1_on = False
            await event.reply("❌ RandomMsg (1m) OFF")

    elif cmd == "/random10":
        if args and args[0].lower() == "on":
            random10_on = True
            await event.reply("✅ RandomMsg (10m) ON")
        elif args and args[0].lower() == "off":
            random10_on = False
            await event.reply("❌ RandomMsg (10m) OFF")

    # --- SPAM ---
    elif cmd == "/spam":
        if args:
            parts = args[0].split(maxsplit=1)
            if len(parts) == 2:
                delay = int(parts[0])
                msg = parts[1]
                # cancel old spam if running
                if chat_id in spam_settings and "task" in spam_settings[chat_id]:
                    spam_settings[chat_id]["task"].cancel()
                task = asyncio.create_task(spam_loop(chat_id, msg, delay))
                spam_settings[chat_id] = {"msg": msg, "delay": delay, "task": task}
                await event.reply(f"✅ Spam ON: '{msg}' every {delay}s")
        else:
            await event.reply("Usage: /spam <delay> <message>")

    elif cmd == "/spamoff":
        if chat_id in spam_settings:
            if "task" in spam_settings[chat_id]:
                spam_settings[chat_id]["task"].cancel()
            spam_settings.pop(chat_id)
            await event.reply("❌ Spam OFF")

    # --- STATUS ---
    elif cmd == "/status":
        ag = "ON" if autograb_global or autograb_status.get(chat_id, False) else "OFF"
        r1 = "ON" if random1_on else "OFF"
        r10 = "ON" if random10_on else "OFF"
        sp = f"{spam_settings[chat_id]['msg']} / {spam_settings[chat_id]['delay']}s" if chat_id in spam_settings else "OFF"

        uptime_sec = int(time.time() - START_TIME)
        hrs, rem = divmod(uptime_sec, 3600)
        mins, secs = divmod(rem, 60)
        uptime_str = f"{hrs}h {mins}m {secs}s"

        await event.reply(
            f"📊 STATUS\n"
            f"Autograb: {ag}\n"
            f"Random1m: {r1}\n"
            f"Random10m: {r10}\n"
            f"Spam: {sp}\n"
            f"⏱ Uptime: {uptime_str}"
        )

# ===== RANDOM LOOPS =====
async def random_loop(delay, text, checker):
    while True:
        await asyncio.sleep(delay)
        if checker():
            await client.send_message(SPECIAL_CHAT, text)

async def spam_loop(chat_id, msg, delay):
    while True:
        await asyncio.sleep(delay)
        await client.send_message(chat_id, msg)

# ===== MAIN =====
async def main():
    await client.start()
    print("✅ Bot Started")

    # start background random tasks
    asyncio.create_task(random_loop(66, "/explore", lambda: random1_on))
    asyncio.create_task(random_loop(620, "/proposee", lambda: random10_on))

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())



