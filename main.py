import os
import asyncio
import html
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)

# Render Web Service Health Check Server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

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
    logging.info(f"Group tracked: {message.chat.id}")

@app.on_message(filters.command("ping"))
async def ping_cmd(_, message: Message):
    await message.reply_text("Pong! Bot is online and working.")

@app.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text("Hello! Bot is active. Add me as admin in your group and use /mtag.")

@app.on_message(filters.command("mtag") & filters.group)
async def mention_all(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None
    
    logging.info(f"/mtag received in group {chat_id} from user {user_id}")

    # Admin Check
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text("Only Group Admins can use this command!")
            return
    except Exception as e:
        logging.error(f"Admin check error: {e}")
        await message.reply_text(f"Admin check failed: {e}")
        return

    if tagging_status.get(chat_id, {}).get("active", False):
        await message.reply_text("Tagging is already running! Use /cancel to stop.")
        return

    custom_text = ""
    if message.reply_to_message:
        custom_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 1:
        custom_text = message.text.split(None, 1)[1]

    tagging_status[chat_id] = {"active": True, "tagged": 0}
    await message.reply_text("Tagging process started...")

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
                    await client.send_message(chat_id, full_message, parse_mode=ParseMode.HTML)
                    await asyncio.sleep(2)
                except Exception as e:
                    logging.error(f"Error sending message: {e}")
                usrnum = 0
                usrtxt = ""

        if usrnum > 0 and tagging_status.get(chat_id, {}).get("active", False):
            full_message = f"{custom_text}\n\n{usrtxt}" if custom_text else usrtxt
            try:
                await client.send_message(chat_id, full_message, parse_mode=ParseMode.HTML)
            except Exception as e:
                logging.error(f"Error sending final message: {e}")

    except Exception as e:
        logging.error(f"Tagging loop error: {e}")
        await message.reply_text(f"Error: {e}")

    was_cancelled = not tagging_status.get(chat_id, {}).get("active", False)
    final_count = tagging_status.get(chat_id, {}).get("tagged", total_tagged)
    tagging_status[chat_id] = {"active": False, "tagged": 0}

    if was_cancelled:
        await message.reply_text(f"Tagging stopped! Total {final_count} members tagged.")
    else:
        await message.reply_text(f"Tagging completed! Total {final_count} members tagged.")

@app.on_message(filters.command(["cancel", "mcancel"]) & filters.group)
async def cancel_tagging(client, message: Message):
    chat_id = message.chat.id
    if tagging_status.get(chat_id, {}).get("active", False):
        tagging_status[chat_id]["active"] = False
        await message.reply_text("Stopping tagging...")
    else:
        await message.reply_text("No active tagging running.")

if __name__ == "__main__":
    app.run()
