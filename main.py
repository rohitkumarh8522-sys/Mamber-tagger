import os
import asyncio
import html
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Debug logging for Render logs
logging.basicConfig(level=logging.INFO)

# Dummy Web Server for Render Free Web Service
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# Pyrogram / Asyncio Event Loop Fix
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus, ParseMode

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

app = Client("tagger_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

tagging_status = {}
active_groups = set()

@app.on_message(filters.group & ~filters.service)
async def track_groups(_, message: Message):
    active_groups.add(message.chat.id)

async def is_admin(client, chat_id, user_id):
    if not user_id:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
        return False

@app.on_message(filters.command("start", prefixes=["/", "!"]))
async def start_cmd(client, message: Message):
    help_text = (
        "👋 **Hello! I am User Tagger Bot.**\n\n"
        "🛠 **How to Use:**\n"
        "1. Add me to your Telegram Group.\n"
        "2. Promote me as **Admin** with full permissions.\n\n"
        "👑 **Group Admin Commands:**\n"
        "• `/mtag <text/link>` - Start continuous tagging for all group members.\n"
        "  *(You can also reply `/mtag` to any link or post)*\n"
        "• `/cancel` or `/mcancel` - Stop the ongoing tagging process.\n\n"
        "⚠️ **Note:** Only Group Admins and Owner can use these commands."
    )
    await message.reply_text(help_text, disable_web_page_preview=True)

# Admin Command: /mtag or !mtag
@app.on_message(filters.command(["mtag", "tagall"], prefixes=["/", "!"]) & filters.group)
async def mention_all(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    logging.info(f"Command /mtag received in Chat ID: {chat_id} from User ID: {user_id}")

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ Only Group Admins can use this command!")
        return

    if tagging_status.get(chat_id, {}).get("active", False):
        await message.reply_text("⚠️ Tagging is already running! Use `/cancel` to stop.")
        return

    custom_text = ""
    if message.reply_to_message:
        custom_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 1:
        custom_text = message.text.split(None, 1)[1]

    tagging_status[chat_id] = {"active": True, "tagged": 0}
    await message.reply_text("🚀 Tagging process started...")

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
            tagging_status[chat_id]["tagged"] = total_tagged

            first_name = html.escape(member.user.first_name or "User")
            
            if usrtxt:
                usrtxt += f' , <a href="tg://user?id={member.user.id}">{first_name}</a>'
            else:
                usrtxt = f'<a href="tg://user?id={member.user.id}">{first_name}</a>'

            if usrnum == 5:
                full_message = f"{custom_text}\n\n{usrtxt}" if custom_text else usrtxt
                try:
                    await client.send_message(chat_id, full_message, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
                    await asyncio.sleep(2)
                except Exception as e:
                    logging.error(f"Error sending tags: {e}")
                usrnum = 0
                usrtxt = ""

        if usrnum > 0 and tagging_status.get(chat_id, {}).get("active", False):
            full_message = f"{custom_text}\n\n{usrtxt}" if custom_text else usrtxt
            try:
                await client.send_message(chat_id, full_message, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            except Exception as e:
                logging.error(f"Error: {e}")

    except Exception as e:
        logging.error(f"Loop error in chat_id {chat_id}: {e}")
        await message.reply_text("❌ Error: Make sure bot is Admin with required rights!")

    was_cancelled = not tagging_status.get(chat_id, {}).get("active", False)
    final_count = tagging_status.get(chat_id, {}).get("tagged", total_tagged)
    tagging_status[chat_id] = {"active": False, "tagged": 0}

    if was_cancelled:
        await message.reply_text(f"🛑 **Tagging Stopped!**\n\nTotal **{final_count}** members were tagged.")
    else:
        await message.reply_text(f"✅ **Tagging Completed!**\n\nTotal **{final_count}** members were tagged.")

# Admin Command: /cancel or /mcancel
@app.on_message(filters.command(["cancel", "mcancel"], prefixes=["/", "!"]) & filters.group)
async def cancel_tagging(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ Only Group Admins can use this command!")
        return

    if tagging_status.get(chat_id, {}).get("active", False):
        current_count = tagging_status[chat_id]["tagged"]
        tagging_status[chat_id]["active"] = False
        await message.reply_text(f"🛑 Stopping tagging...\nTagged **{current_count}** members so far.")
    else:
        await message.reply_text("ℹ️ No active tagging in this group.")

# Hidden Owner Command: /groups
@app.on_message(filters.command("groups", prefixes=["/", "!"]))
async def list_groups(client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id != OWNER_ID:
        return
    count = len(active_groups)
    await message.reply_text(f"📊 **Bot Status:**\n\nActive in **{count}** groups.")

# Hidden Owner Command: /broadcast
@app.on_message(filters.command("broadcast", prefixes=["/", "!"]))
async def broadcast_msg(client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if user_id != OWNER_ID:
        return

    if not message.reply_to_message and len(message.command) < 2:
        await message.reply_text("📢 **Broadcast Usage:**\n`/broadcast <text>` or reply to a message.")
        return

    sent_count = 0
    failed_count = 0
    status_msg = await message.reply_text("⏳ Broadcasting message...")

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
        f"📢 **Broadcast Completed!**\n\n"
        f"✅ Success: **{sent_count}** groups\n"
        f"❌ Failed: **{failed_count}** groups"
    )

if __name__ == "__main__":
    app.run()
