import logging
import sqlite3
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ChatMemberHandler

# ==== CONFIG ====
TOKEN = os.getenv("TOKEN")  # Will come from Render env
MAIN_GROUP_ID = -5049946456      # ← CHANGE TO YOUR MAIN GROUP ID
ADMIN_GROUP_ID = -5083806344     # ← CHANGE TO YOUR ADMIN GROUP ID

BAD_WORDS = ['fuck','chut','bc','mc','gandu','randi','loda','bhosdike','madarchod','behenchod','shit','asshole','cunt']

# Permanent DB path (works with Render disk)
DB_NAME = '/opt/render/project/study_security.db'   # ← THIS IS THE MAGIC LINE

logging.basicConfig(level=logging.INFO)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 user_id INTEGER PRIMARY KEY,
                 reg_no TEXT UNIQUE NOT NULL,
                 verified INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🔐 Security Check\n\n"
        "Send your 8-digit coaching registration number only.\n"
        "Example: 22041234\n\n"
        "Exactly 8 numbers, no space, no letters."
    )

async def handle_reg_no(update: Update, context: CallbackContext):
    user = update.message.from_user
    text = update.message.text.strip()
    
    if not re.fullmatch(r'\d{8}', text):
        await update.message.reply_text("❌ Invalid format!\nSend exactly 8 digits.\nExample: 22241234")
        return
    
    reg_no = text
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE reg_no = ?", (reg_no,))
    if c.fetchone():
        await update.message.reply_text("❌ This reg no is already taken!")
        conn.close()
        return
    
    c.execute("INSERT OR REPLACE INTO users (user_id, reg_no, verified) VALUES (?, ?, 1)", (user.id, reg_no))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Verified! You can now use the grp 📚")
    
    await context.bot.send_message(ADMIN_GROUP_ID, 
        f"✅ New Verified\nName: {user.full_name}\n@{user.username or 'No username'}\nID: {user.id}\nReg No: {reg_no}")
    
    # Limited permissions
    from telegram import ChatPermissions
    await context.bot.restrict_chat_member(
        chat_id=MAIN_GROUP_ID,
        user_id=user.id,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_photos=True,
            can_send_videos=False,
            can_send_documents=False,
            can_send_audios=False,
            can_send_voice_notes=False,
            can_send_video_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_invite_users=True
        )
    )

async def new_member(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        if member.is_bot: continue
        await context.bot.restrict_chat_member(MAIN_GROUP_ID, member.id, permissions=ChatPermissions())
        keyboard = [[InlineKeyboardButton("🔐 Verify Now", url=f"t.me/{context.bot.username}")]]
        try:
            await context.bot.send_message(member.id,
                "🔒 Secure Study Group\nClick below & send your 8-digit reg no to join.",
                reply_markup=InlineKeyboardMarkup(keyboard))
        except: pass

async def check_message(update: Update, context: CallbackContext):
    msg = update.message
    if msg.chat_id != MAIN_GROUP_ID or not msg.from_user: return
    
    user_id = msg.from_user.id
    text = (msg.text or msg.caption or "").lower()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or row[0] == 0:
        await msg.delete()
        return
    
    for word in BAD_WORDS:
        if word in text:
            await context.bot.ban_chat_member(MAIN_GROUP_ID, user_id)
            await msg.delete()
            await context.bot.send_message(ADMIN_GROUP_ID,
                f"🚨 BANNED for bad word\nUser: {msg.from_user.full_name} (@{msg.from_user.username})\nID: {user_id}\nMsg: {msg.text or msg.caption}")
            break

# Keep-alive ping endpoint (prevents sleeping)
async def ping(update: Update, context: CallbackContext):
    await update.message.reply_text("Bot is alive master 🔥")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start, filters.ChatType.PRIVATE))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_reg_no))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    app.add_handler(MessageHandler(filters.ALL & filters.Chat(MAIN_GROUP_ID), check_message))
    app.add_handler(CommandHandler("ping", ping))  # for uptime
    
    print("🤖 KOTA STUDY SECURITY BOT LIVE 24/7")
    app.run_polling()

if __name__ == '__main__':
    main()
