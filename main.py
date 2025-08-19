import os, json, asyncio, time, threading
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto

# ==== CONFIG ====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_STRING")
OWNER_ID = int(os.getenv("OWNER_ID"))  # Your Telegram ID
DB_FILE = "db.json"
SPECIAL_CHAT = int(os.getenv("SPECIAL_CHAT", 0))  # chat for random msgs
WAIFU_BOT_ID = 7438162678  # bot id for autograb
GRAB_KEYWORD = " ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀꜱ ᴀᴘᴘᴇᴀʀᴇᴅ!"

# ==== LOAD DB ====
def load_db():
    global DB
    if not os.path.exists(DB_FILE):
        DB = {}
    else:
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                DB = json.load(f)
        except json.JSONDecodeError:
            print("Error reading DB file, starting with empty database")
            DB = {}

def save_db():
    """Save database with error handling"""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(DB, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving database: {e}")
        return False

load_db()

# ==== STATES ====
chat_states = {}  # {chat_id: {"grab": True, "spam": False}}
grab_global = True
spam_tasks = {}
random_tasks = {"1m": None, "10m": None}
random_state = {"1m": False, "10m": False}
bot_start_time = time.time()  # Track bot uptime

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

# ==== UNIQUE IMAGE ID FUNCTIONS ====
def get_unique_image_id(photo):
    """
    Extract unique image ID from photo object
    Try multiple methods for stability
    """
    try:
        # Method 1: Use file_reference if available (most stable)
        if hasattr(photo, 'file_reference') and photo.file_reference:
            return f"ref_{photo.file_reference.hex()}"
        
        # Method 2: Combine multiple photo attributes
        if hasattr(photo, 'id') and hasattr(photo, 'dc_id'):
            unique_id = f"{photo.id}_{photo.dc_id}"
            if hasattr(photo, 'date'):
                unique_id += f"_{photo.date}"
            return unique_id
            
        # Method 3: Use photo ID with access_hash (your original method, improved)
        if hasattr(photo, 'id') and hasattr(photo, 'access_hash'):
            return f"{photo.id}_{photo.access_hash}"
        
        # Method 4: Use photo ID with size info for uniqueness
        if hasattr(photo, 'id') and hasattr(photo, 'sizes') and photo.sizes:
            largest_size = max(photo.sizes, key=lambda s: getattr(s, 'size', 0) if hasattr(s, 'size') else 0)
            if hasattr(largest_size, 'type'):
                return f"{photo.id}_{largest_size.type}"
        
        # Fallback: Just use photo ID
        return str(photo.id) if hasattr(photo, 'id') else None
        
    except Exception as e:
        print(f"Error extracting unique image ID: {e}")
        return None

def find_character_by_id(image_id):
    """Find character name by unique image ID in database"""
    if not image_id:
        return None
        
    # Direct lookup
    if image_id in DB:
        return DB[image_id]
    
    # Try variations of the ID (in case format changed)
    for stored_id, char_name in DB.items():
        if isinstance(char_name, str):
            # Try matching core ID parts
            if '_' in image_id and '_' in stored_id:
                current_parts = image_id.split('_')
                stored_parts = stored_id.split('_')
                # Match first part (usually the main ID)
                if len(current_parts) > 0 and len(stored_parts) > 0:
                    if current_parts[0] == stored_parts[0]:
                        return char_name
    
    return None

# ==== AUTOGRAB ====
@client.on(events.NewMessage())
async def handler(event):
    try:
        # Check if grab is enabled for this chat
        if not is_grab_on(event.chat_id):
            return
            
        # Check if message is from the waifu bot (if specified)
        if WAIFU_BOT_ID and event.sender_id != WAIFU_BOT_ID:
            return
            
        # Check if message has photo
        if not event.message or not event.media:
            return
        if not isinstance(event.media, MessageMediaPhoto):
            return
            
        # Check if message contains the grab keyword
        message_text = event.message.message or ""
        if GRAB_KEYWORD.lower() not in message_text.lower():
            return
            
        print(f"Processing potential grab message in chat {event.chat_id}")
        print(f"Message text: {message_text[:100]}")
        
        # Extract unique image ID
        photo = event.media.photo
        unique_id = get_unique_image_id(photo)
        
        if not unique_id:
            print("Failed to extract unique image ID")
            return
            
        print(f"Extracted unique ID: {unique_id}")
        
        # Find character in database
        character_name = find_character_by_id(unique_id)
        
        if character_name:
            print(f"Found character: {character_name}")
            await event.reply(f"/grab {character_name}")
        else:
            print("Character not found in database")
            # Log unknown image ID for debugging
            try:
                with open("unknown_images.log", "a", encoding="utf-8") as f:
                    f.write(f"{time.time()}: {unique_id} - {message_text[:50]}\n")
            except Exception as log_error:
                print(f"Failed to log unknown image: {log_error}")
                
    except Exception as e:
        print(f"Error in autograb handler: {e}")
        import traceback
        traceback.print_exc()

# ==== DATABASE MANAGEMENT ====
@client.on(events.NewMessage(pattern=r"^/addchar (.+)$"))
@owner_only
async def add_character(event):
    """Add character to database by replying to a message with image"""
    char_name = event.pattern_match.group(1).strip()
    
    # Check if replying to a message with photo
    try:
        reply = await event.get_reply_message()
    except Exception:
        reply = None
        
    if not reply or not reply.media or not isinstance(reply.media, MessageMediaPhoto):
        await event.reply("❌ Reply to a message with an image to add character")
        return
    
    try:
        # Extract unique image ID
        photo = reply.media.photo
        unique_id = get_unique_image_id(photo)
        
        if not unique_id:
            await event.reply("❌ Failed to extract unique image ID")
            return
            
        # Add to database
        DB[unique_id] = char_name
        
        # Save database
        if save_db():
            await event.reply(f"✅ Added {char_name} to database\nID: `{unique_id}`")
            print(f"Added character: {char_name} with ID: {unique_id}")
        else:
            await event.reply("❌ Failed to save database")
        
    except Exception as e:
        await event.reply(f"❌ Error adding character: {e}")
        print(f"Error adding character: {e}")

@client.on(events.NewMessage(pattern=r"^/dbinfo$"))
@owner_only
async def db_info(event):
    """Show database information"""
    if not DB:
        await event.reply("📚 Database is empty")
        return
    
    total = len(DB)
    sample = list(DB.items())[:5]  # Show first 5 entries
    
    msg = f"📚 Database Info:\n"
    msg += f"Total entries: {total}\n\n"
    msg += "Sample entries:\n"
    for img_id, char_name in sample:
        short_id = img_id[:20] + "..." if len(img_id) > 20 else img_id
        msg += f"`{short_id}` → {char_name}\n"
    
    if total > 5:
        msg += f"\n... and {total - 5} more entries"
    
    await event.reply(msg)

# ==== SPAM ====
async def spam_loop(chat_id, msg, delay):
    try:
        while chat_states.get(chat_id, {}).get("spam", False):
            await client.send_message(chat_id, msg)
            await asyncio.sleep(delay)
    except Exception as e:
        print(f"Error in spam loop: {e}")
        chat_states.setdefault(chat_id, {})["spam"] = False

@client.on(events.NewMessage(pattern=r"^/spam (.+) (\d+)$"))
@owner_only
async def start_spam(event):
    chat_id = event.chat_id
    msg, delay = event.pattern_match.groups()
    delay = int(delay)
    
    if delay < 1:
        await event.reply("❌ Delay must be at least 1 second")
        return
        
    chat_states.setdefault(chat_id, {})["spam"] = True
    if chat_id in spam_tasks:
        try: 
            spam_tasks[chat_id].cancel()
        except: 
            pass
    spam_tasks[chat_id] = asyncio.create_task(spam_loop(chat_id, msg, delay))
    await event.reply(f"✅ Spamming `{msg}` every {delay}s")

@client.on(events.NewMessage(pattern=r"^/spam off$"))
@owner_only
async def stop_spam(event):
    chat_id = event.chat_id
    chat_states.setdefault(chat_id, {})["spam"] = False
    if chat_id in spam_tasks:
        try: 
            spam_tasks[chat_id].cancel()
        except: 
            pass
        del spam_tasks[chat_id]
    await event.reply("🛑 Spam stopped")

# ==== RANDOM MESSAGES ====
async def random_loop(chat_id, delay, key):
    try:
        msgs = random_msgs[key]
        i = 0
        while random_state[key]:
            await client.send_message(chat_id, msgs[i % len(msgs)])
            i += 1
            await asyncio.sleep(delay)
    except Exception as e:
        print(f"Error in random loop {key}: {e}")
        random_state[key] = False

@client.on(events.NewMessage(pattern=r"^/random1 on$"))
@owner_only
async def random1_on(event):
    if SPECIAL_CHAT and event.chat_id != SPECIAL_CHAT:
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
    if SPECIAL_CHAT and event.chat_id != SPECIAL_CHAT:
        return
    random_state["1m"] = False
    if random_tasks["1m"]:
        try: random_tasks["1m"].cancel()
        except: pass
    await event.reply("🛑 Random1 OFF")

@client.on(events.NewMessage(pattern=r"^/random2 on$"))
@owner_only
async def random2_on(event):
    if SPECIAL_CHAT and event.chat_id != SPECIAL_CHAT:
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
    if SPECIAL_CHAT and event.chat_id != SPECIAL_CHAT:
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
    # Calculate uptime
    uptime_seconds = int(time.time() - bot_start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    st = chat_states.get(event.chat_id, {})
    msg = f"""📊 Status:
⏰ Uptime: {uptime_str}
🌍 Grab Global: {"✅" if grab_global else "❌"}
🎯 Grab Here: {"✅" if st.get("grab", False) else "❌"}
💬 Spam: {"✅" if st.get("spam", False) else "❌"}
🎲 Random1: {"✅" if random_state["1m"] else "❌"}
🎲 Random2: {"✅" if random_state["10m"] else "❌"}
📚 DB Entries: {len(DB)}
"""
    await event.reply(msg)

# ==== TELEGRAM BOT RUNNER ====
async def start_bot():
    """Start the telegram bot"""
    try:
        print("🚀 Bot starting...")
        await client.start()
        print("✅ Bot connected successfully!")
        
        # Get bot info
        me = await client.get_me()
        print(f"📱 Running as: {me.first_name} ({me.username})")
        
        await client.run_until_disconnected()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()

# ==== MAIN EXECUTION ====
if __name__ == "__main__":
    # Import keep_alive here to avoid circular imports
    try:
        from keep_alive import keep_alive
        # Start the Flask keep-alive server in a separate thread
        keep_alive()
        print("🌐 Keep-alive server started")
    except ImportError:
        print("⚠️ keep_alive.py not found, running without keep-alive server")
    except Exception as e:
        print(f"⚠️ Error starting keep-alive server: {e}")
    
    # Start the bot
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()








