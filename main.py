import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

# Environment variables
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

app = Client("tagger_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

tagging_chats = {}
groups_list = set()

# Group me aane wale messages se active groups count track hoga
@app.on_message(filters.group & ~filters.service)
async def track_groups(_, message: Message):
    groups_list.add(message.chat.id)

@app.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply_text("Namaste! Main Tagger Bot hu. Group me admin banao aur /mtag use karo.")

# Admin Command: /mtag (10 members per batch)
@app.on_message(filters.command("mtag") & filters.group)
async def mention_all(client, message: Message):
    chat_id = message.chat.id
    
    try:
        user = await client.get_chat_member(chat_id, message.from_user.id)
        if user.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text("Ye command sirf Group Admins ke liye hai!")
            return
    except Exception:
        return

    if tagging_chats.get(chat_id, False):
        await message.reply_text("Tagging pehle se chal raha hai. Stop karne ke liye /cancel use karein.")
        return

    tagging_chats[chat_id] = True

    custom_text = ""
    if message.reply_to_message:
        custom_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 1:
        custom_text = message.text.split(None, 1)[1]
    else:
        custom_text = "Everyone check this out!"

    usrnum = 0
    usrtxt = ""
    
    try:
        async for member in client.get_chat_members(chat_id):
            if not tagging_chats.get(chat_id, False):
                await message.reply_text("Tagging process cancel kar diya gaya hai.")
                return

            if member.user.is_bot or member.user.is_deleted:
                continue

            usrnum += 1
            usrtxt += f"[{member.user.first_name}](tg://user?id={member.user.id}) "

            if usrnum == 10:
                full_message = f"{custom_text}\n\n{usrtxt}"
                try:
                    await client.send_message(chat_id, full_message, disable_web_page_preview=True)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"Error: {e}")
                usrnum = 0
                usrtxt = ""

        if usrnum > 0 and tagging_chats.get(chat_id, False):
            full_message = f"{custom_text}\n\n{usrtxt}"
            try:
                await client.send_message(chat_id, full_message, disable_web_page_preview=True)
            except Exception as e:
                print(f"Error: {e}")

    except Exception as e:
        await message.reply_text("Error: Make sure bot is Admin with proper rights!")

    tagging_chats[chat_id] = False
    await message.reply_text("Sabhi members ko tag kar diya gaya hai!")

# Admin Command: /cancel
@app.on_message(filters.command("cancel") & filters.group)
async def cancel_tagging(client, message: Message):
    chat_id = message.chat.id
    
    try:
        user = await client.get_chat_member(chat_id, message.from_user.id)
        if user.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply_text("Sirf Admin he tag cancel kar sakte hain.")
            return
    except Exception:
        return

    if tagging_chats.get(chat_id, False):
        tagging_chats[chat_id] = False
        await message.reply_text("Tagging process rok diya gaya hai.")
    else:
        await message.reply_text("Koi active tagging nahi chal raha hai.")

# Owner Command: /groups
@app.on_message(filters.command("groups"))
async def list_groups(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.reply_text(f"Bot abhi total **{len(groups_list)}** groups me active hai.")

# Owner Command: /broadcast
@app.on_message(filters.command("broadcast"))
async def broadcast_msg(client, message: Message):
    if message.from_user.id != OWNER_ID:
        return

    if not message.reply_to_message and len(message.command) < 2:
        await message.reply_text("Broadcast karne ke liye text likhein ya kisi message ko reply karein.")
        return

    sent_count = 0
    failed_count = 0

    for g_id in list(groups_list):
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

    await message.reply_text(f"Broadcast poora hua!\nSuccess: {sent_count}\nFailed: {failed_count}")

if __name__ == "__main__":
    app.run()