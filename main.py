import os
import asyncio

# Render / Newer Python Event Loop Fix
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

# Environment Variables
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

app = Client("tagger_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Active state tracking
tagging_status = {}  # chat_id -> {"active": bool, "tagged_count": int}
active_groups = set()

# Automatically track active groups
@app.on_message(filters.group & ~filters.service)
async def track_groups(_, message: Message):
    active_groups.add(message.chat.id)

# Helper function to check admin rights
async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

# Command: /start
@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    user_id = message.from_user.id
    
    help_text = (
        "👋 **नमस्ते! मैं All-Member Tagging Bot हूँ।**\n\n"
        "🛠 **बॉट का उपयोग कैसे करें:**\n"
        "1. सबसे पहले मुझे अपने टेलीग्राम ग्रुप में जोड़ें।\n"
        "2. मुझे ग्रुप का **Admin** बनाएं (ताकि मैं मेंबर्स को टैग कर सकूँ)।\n\n"
        "👑 **ग्रुप एडमिन कमांड्स:**\n"
        "• `/mtag <टेक्स्ट या लिंक>` - ग्रुप के सभी मेंबर्स को 10-10 के बैच में टैग करना शुरू करें।\n"
        "  *(आप किसी फोटो या मैसेज को रिप्लाई करके भी `/mtag` लिख सकते हैं)*\n"
        "• `/cancel` - टैग करने की प्रक्रिया को बीच में ही रोकें।\n\n"
        "⚠️ **नोट:** ये कमांड्स सिर्फ ग्रुप Admin या Owner ही चला सकते हैं।"
    )
    
    # Show hidden commands only to Bot Owner in private chat
    if user_id == OWNER_ID and message.chat.type.name == "PRIVATE":
        help_text += (
            "\n\n🔐 **बॉट ओनर कमांड्स (Hidden):**\n"
            "• `/groups` - बॉट कितने ग्रुप्स में एक्टिव है देखें।\n"
            "• `/broadcast <मैसेज या रिप्लाई>` - सभी ग्रुप्स में ब्रॉडकास्ट भेजें।"
        )
        
    await message.reply_text(help_text, disable_web_page_preview=True)

# Admin Command: /mtag
@app.on_message(filters.command("mtag") & filters.group)
async def mention_all(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Admin check
    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ यह कमांड सिर्फ ग्रुप Admin या Owner ही इस्तेमाल कर सकते हैं!")
        return

    # Check if already running
    if tagging_status.get(chat_id, {}).get("active", False):
        await message.reply_text("⚠️ इस ग्रुप में टैगिंग पहले से चल रही है! रोकने के लिए `/cancel` लिखें।")
        return

    # Custom text/link extraction
    custom_text = ""
    if message.reply_to_message:
        custom_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 1:
        custom_text = message.text.split(None, 1)[1]
    else:
        custom_text = "📢 ध्यान दें सभी मेंबर्स!"

    # Initialize status
    tagging_status[chat_id] = {"active": True, "tagged_count": 0}
    await message.reply_text("🚀 टैगिंग प्रक्रिया शुरू हो रही है... (प्रति मैसेज 10 मेंबर्स)")

    usrnum = 0
    usrtxt = ""
    total_tagged = 0

    try:
        async for member in client.get_chat_members(chat_id):
            if not tagging_status.get(chat_id, {}).get("active", False):
                break

            if member.user.is_bot or member.user.is_deleted:
                continue

            usrnum += 1
            total_tagged += 1
            tagging_status[chat_id]["tagged_count"] = total_tagged
            
            first_name = member.user.first_name or "User"
            usrtxt += f"[{first_name}](tg://user?id={member.user.id}) "

            # Batch of 10
            if usrnum == 10:
                full_message = f"{custom_text}\n\n{usrtxt}"
                try:
                    await client.send_message(chat_id, full_message, disable_web_page_preview=True)
                    await asyncio.sleep(3)  # Safe delay between batches
                except Exception as e:
                    print(f"Error sending tag in {chat_id}: {e}")
                usrnum = 0
                usrtxt = ""

        # Remaining members (< 10)
        if usrnum > 0 and tagging_status.get(chat_id, {}).get("active", False):
            full_message = f"{custom_text}\n\n{usrtxt}"
            try:
                await client.send_message(chat_id, full_message, disable_web_page_preview=True)
            except Exception as e:
                print(f"Error sending remaining tag in {chat_id}: {e}")

    except Exception:
        await message.reply_text("❌ त्रुटि: कृपया सुनिश्चित करें कि बॉट ग्रुप का Admin है।")

    # Finish message
    was_cancelled = not tagging_status.get(chat_id, {}).get("active", False)
    final_count = tagging_status.get(chat_id, {}).get("tagged_count", total_tagged)
    tagging_status[chat_id] = {"active": False, "tagged_count": 0}

    if was_cancelled:
        await message.reply_text(f"🛑 **टैगिंग प्रक्रिया रोक दी गई है!**\n\nकुल **{final_count}** मेंबर्स को टैग किया गया।")
    else:
        await message.reply_text(f"✅ **टैगिंग पूर्ण हो गई है!**\n\nकुल **{final_count}** मेंबर्स को टैग किया गया।")

# Admin Command: /cancel
@app.on_message(filters.command("cancel") & filters.group)
async def cancel_tagging(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ यह कमांड सिर्फ ग्रुप Admin या Owner ही इस्तेमाल कर सकते हैं!")
        return

    if tagging_status.get(chat_id, {}).get("active", False):
        current_count = tagging_status[chat_id]["tagged_count"]
        tagging_status[chat_id]["active"] = False
        await message.reply_text(f"🛑 टैगिंग रोकी जा रही है...\nअब तक **{current_count}** मेंबर्स को टैग किया जा चुका है।")
    else:
        await message.reply_text("ℹ️ इस ग्रुप में कोई टैगिंग चालू नहीं है।")

# Bot Owner Command: /groups (Hidden)
@app.on_message(filters.command("groups"))
async def list_groups(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return  # Silently ignore non-owners

    count = len(active_groups)
    await message.reply_text(f"📊 **बॉट स्टेटस:**\n\nबॉट अभी कुल **{count}** ग्रुप्स में एक्टिव है।")

# Bot Owner Command: /broadcast (Hidden)
@app.on_message(filters.command("broadcast"))
async def broadcast_msg(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return  # Silently ignore non-owners

    if not message.reply_to_message and len(message.command) < 2:
        await message.reply_text("📢 **ब्रॉडकास्ट उपयोग:**\n`/broadcast <मैसेज>` या किसी मैसेज को रिप्लाई करके `/broadcast` लिखें।")
        return

    sent_count = 0
    failed_count = 0

    status_msg = await message.reply_text("⏳ ब्रॉडकास्ट भेजा जा रहा है...")

    for g_id in list(active_groups):
        try:
            if message.reply_to_message:
                await message.reply_to_message.copy(g_id)
            else:
                broadcast_text = message.text.split(None, 1)[1]
                await client.send_message(g_id, broadcast_text)
            sent_count += 1
            await asyncio.sleep(1)
        except Exception:
            failed_count += 1

    await status_msg.edit_text(
        f"📢 **ब्रॉडकास्ट प्रक्रिया पूरी हुई!**\n\n"
        f"✅ सफ़ल: **{sent_count}** ग्रुप्स\n"
        f"❌ असफ़ल: **{failed_count}** ग्रुप्स"
    )

if __name__ == "__main__":
    app.run()
