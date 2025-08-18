import os, json, time, random, asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from keep_alive import keep_alive

# ===== CONFIG =====
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION = os.environ.get("SESSION", "")
OWNER = os.environ.get("OWNER", "your_username")  # who can control bot
SPECIAL_CHAT = int(os.environ.get("SPECIAL_CHAT", "0"))  # chat for random msgs
WAIFU_BOT = os.environ.get("WAIFU_BOT", "waifubot_username")  # bot to grab from

# ===== STATE =====
with open("db.json", "r") as f:
    WAIFU_DB = json.load(f)

grabbing_on = False
randommsg1_on = False
randommsg2_on = False
spam_settings = {}  # chat_id -> { "delay": int, "message": str, "on": bool }

# random messages (EDIT HERE for custom text)
RANDOM_MSG1_TEXT = "/explore"
RANDOM_MSG2_TEXT = "marry"

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# ===== HELPERS =====
async def is_owner(event):
    sender = await event.get_sender()
    return (sender.username or "").lower() == OWNER.lower()

# ===== AUTOGRAB =====
@client.on(events.NewMessage)
async def autograb(event):
    global grabbing_on
    if not grabbing_on: return
    if not event.is_group: return
    if not event.sender.bot: return  # must be from a bot
    if (event.sender.username or "").lower() != WAIFU_BOT.lower():
        return  # only from waifu bot
    
    if event.photo:
        file_id = str(event.photo.id)
        if file_id in WAIFU_DB:
            name = WAIFU_DB[file_id]
            await event.reply(f"/grab {name}")

# ===== RANDOM MESSAGES =====
async def random_msg_loop1():
    global randommsg1_on
    while True:
        if randommsg1_on:
            await client.send_message(SPECIAL_CHAT, RANDOM_MSG1_TEXT)
        await asyncio.sleep(65)  # 1 min

async def random_msg_loop2():
    global randommsg2_on
    while True:
        if randommsg2_on:
            await client.send_message(SPECIAL_CHAT, RANDOM_MSG2_TEXT)
        await asyncio.sleep(605)  # 10 min

# ===== SPAM SYSTEM =====
async def spam_loop(chat_id):
    while True:
        if chat_id in spam_settings and spam_settings[chat_id]["on"]:
            msg = spam_settings[chat_id]["message"]
            await client.send_message(chat_id, msg)
        await asyncio.sleep(spam_settings.get(chat_id, {}).get("delay", 5))

# ===== COMMANDS =====
@client.on(events.NewMessage(pattern=r"^/grabbing (on|off)$"))
async def toggle_grabbing(event):
    global grabbing_on
    if not await is_owner(event): return
    grabbing_on = (event.pattern_match.group(1).lower() == "on")
    await event.reply(f"✅ Autograb {'enabled' if grabbing_on else 'disabled'}.")

@client.on(events.NewMessage(pattern=r"^/randommsg1 (on|off)$"))
async def toggle_msg1(event):
    global randommsg1_on
    if not await is_owner(event): return
    randommsg1_on = (event.pattern_match.group(1).lower() == "on")
    await event.reply(f"✅ RandomMsg1 {'enabled' if randommsg1_on else 'disabled'}.")

@client.on(events.NewMessage(pattern=r"^/randommsg2 (on|off)$"))
async def toggle_msg2(event):
    global randommsg2_on
    if not await is_owner(event): return
    randommsg2_on = (event.pattern_match.group(1).lower() == "on")
    await event.reply(f"✅ RandomMsg2 {'enabled' if randommsg2_on else 'disabled'}.")

@client.on(events.NewMessage(pattern=r"^/delay (\d+)$"))
async def set_delay(event):
    if not await is_owner(event): return
    sec = int(event.pattern_match.group(1))
    chat_id = event.chat_id
    if chat_id not in spam_settings:
        spam_settings[chat_id] = {"delay": sec, "message": "hi", "on": True}
        asyncio.create_task(spam_loop(chat_id))
    else:
        spam_settings[chat_id]["delay"] = sec
    await event.reply(f"✅ Spam delay set to {sec} sec in this chat.")

@client.on(events.NewMessage(pattern=r"^/spam (.+)$"))
async def set_spam_msg(event):
    if not await is_owner(event): return
    msg = event.pattern_match.group(1)
    chat_id = event.chat_id
    if chat_id not in spam_settings:
        spam_settings[chat_id] = {"delay": 5, "message": msg, "on": True}
        asyncio.create_task(spam_loop(chat_id))
    else:
        spam_settings[chat_id]["message"] = msg
        spam_settings[chat_id]["on"] = True
    await event.reply(f"✅ Spam ON with message: {msg}")

@client.on(events.NewMessage(pattern=r"^/spam off$"))
async def spam_off(event):
    if not await is_owner(event): return
    chat_id = event.chat_id
    if chat_id in spam_settings:
        spam_settings[chat_id]["on"] = False
    await event.reply("✅ Spam disabled in this chat.")

# ===== STARTUP =====
async def main():
    await client.start()
    print("✅ Bot Started")
    asyncio.create_task(random_msg_loop1())
    asyncio.create_task(random_msg_loop2())
    await client.run_until_disconnected()

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
