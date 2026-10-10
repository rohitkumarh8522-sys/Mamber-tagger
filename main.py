import os
import asyncio
import html
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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

# Event Loop Fix
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

tagging_status = {}  # chat_id -> {"active": bool, "tagged": int}
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
    except Exception:
        return False

@app.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    help_text = (
        "<b>Hello! I am User Tagger Bot.</b>\n\n"
        "<b>How to use:</b>\n"
        "1. Add me to your group and make me <b>Admin</b>.\n"
        "2. Reply to any message/link with <code>/mtag</code> to start tagging 10 members per batch.\n"
        "3. Use <code>/mstop</code> or <code>/cancel</code> to stop tagging."
    )
    await message.reply_text(help_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@app.on_message(filters.command("mtag") & filters.group)
async def mention_all(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id if user else None
    user_name = user.first_name if user else "Admin"

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("Only Group Admins can use this command!")
        return

    if tagging_status.get(chat_id, {}).get("active", False):
        await message.reply_text("Tagging is already running! Use /mstop to stop.")
        return

    # Extract replied message text/caption or command text
    custom_text = ""
    if message.reply_to_message:
        replied = message.reply_to_message
        custom_text = replied.text or replied.caption or "Check this out!"
    elif len(message.command) > 1:
        custom_text = message.text.split(None, 1)[1]
    else:
        custom_text = "Attention everyone!"

    custom_text = html.escape(custom_text)

    tagging_status[chat_id] = {"active": True, "tagged": 0}
    await message.reply_text(f"🚀 Tagging started by <b>{html.escape(user_name)}</b>! (10 members per batch)", parse_mode=ParseMode.HTML)

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
            usrtxt += f'<a href="tg://user?id={member.user.id}">{first_name}</a> '

            # Batch of 10 members
            if usrnum == 10:
                full_message = f"{custom_text}\n\n{usrtxt}"
                try:
                    await client.send_message(chat_id, full_message, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
                    await asyncio.sleep(2.5)
                except Exception as e:
                    print(f"Error: {e}")
                usrnum = 0
                usrtxt = ""

        # Remaining members (< 10)
        if usrnum > 0 and tagging_status.get(chat_id, {}).get("active", False):
            full_message = f"{custom_text}\n\n{usrtxt}"
            try:
                await client.send_message(chat_id, full_message, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            except Exception as e:
                print(f"Error: {e}")

    except Exception as e:
        print(f"Loop error: {e}")
        await message.reply_text(f"Error: Make sure bot is Admin with proper rights! ({e})")

    was_cancelled = not tagging_status.get(chat_id, {}).get("active", False)
    final_count = tagging_status.get(chat_id, {}).get("tagged", total_tagged)
    tagging_status[chat_id] = {"active": False, "tagged": 0}

    if not was_cancelled:
        await message.reply_text(f"✅ Tagging completed! Total <b>{final_count}</b> members tagged.", parse_mode=ParseMode.HTML)

@app.on_message(filters.command(["mstop", "cancel", "mcancel"]) & filters.group)
async def stop_tagging(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_id = user.id if user else None
    user_name = user.first_name if user else "Admin"

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("Only Group Admins can use this command!")
        return

    if tagging_status.get(chat_id, {}).get("active", False):
        current_count = tagging_status[chat_id]["tagged"]
        tagging_status[chat_id]["active"] = False
        await message.reply_text(f"🛑 Tagging stopped by <b>{html.escape(user_name)}</b>!\nTotal <b>{current_count}</b> members tagged so far.", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text("No active tagging running in this group.")

@app.on_message(filters.command("groups"))
async def list_groups(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.reply_text(f"Bot is active in <b>{len(active_groups)}</b> groups.", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("broadcast"))
async def broadcast_msg(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return

    if not message.reply_to_message and len(message.command) < 2:
        await message.reply_text("Usage: /broadcast <text> or reply to a message.")
        return

    sent = 0
    for g_id in list(active_groups):
        try:
            if message.reply_to_message:
                await message.reply_to_message.copy(g_id)
            else:
                text = message.text.split(None, 1)[1]
                await client.send_message(g_id, text)
            sent += 1
            await asyncio.sleep(1)
        except Exception:
            pass
    await message.reply_text(f"Broadcast completed to {sent} groups.")

if __name__ == "__main__":
    app.run()
