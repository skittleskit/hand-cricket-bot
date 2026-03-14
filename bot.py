import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

import config


# =========================
# DATABASE
# =========================

def load_db():
    try:
        with open("database.json", "r") as f:
            data = json.load(f)
    except:
        data = {}

    data.setdefault("captains", {})
    data.setdefault("message_map", {})
    data.setdefault("admins", [config.OWNER_ID])
    data.setdefault("registration_status", False)
    data.setdefault("tournament_name", "Dice Pe Destiny League")
    data.setdefault("users", [])

    return data


def save_db(data):
    with open("database.json", "w") as f:
        json.dump(data, f, indent=4)


# =========================
# ADMIN CHECK
# =========================

def is_admin(user_id):
    db = load_db()
    return user_id in db["admins"]


# =========================
# MAIN MENU
# =========================

def main_menu():
    keyboard = [
        # Row 1: 1 button centered
        [InlineKeyboardButton("📝 Register Team", callback_data="register")],
        
        # Row 2: 2 buttons side by side
        [
            InlineKeyboardButton("🖇️ Colesium", url="https://t.me/DpdL_Gc"),
            InlineKeyboardButton("📜 Rules", callback_data="rules")
        ],
        
        # Row 3: 1 button centered
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")]
    ]

    return InlineKeyboardMarkup(keyboard)

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    db = load_db()

    user = update.effective_user.first_name
    user_id = update.effective_user.id

    # Save user for broadcast
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

    text = f"""
<b>🏏 {db['tournament_name']}</b>
<u>Official tournament registration system</u>

<blockquote>
Welcome, <b>{user}</b>.

Register your team and compete with the strongest
players in the league.
</blockquote>

<b>Features</b>

• Team registration  
• Tournament announcements  
• Direct admin support  
• Match coordination  

<blockquote>
<i>Use the menu below to continue.</i>
</blockquote>
"""
    
    with open("banner.png", "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )
# =========================
# MENU HANDLER
# =========================

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "rules":
        await rules(update, context)

    elif query.data == "faq":
        await faq(update, context)

    elif query.data == "register":
        await register(update, context)


# =========================
# RULES
# =========================

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
📜 TOURNAMENT RULEBOOK

━━━━━━━━━━━━━━━━━━━━

1️⃣ One captain per team

2️⃣ Use /register to apply

3️⃣ Fake registrations
lead to disqualification

4️⃣ Respect all players

5️⃣ Follow match timing

━━━━━━━━━━━━━━━━━━━━
"""

    await update.effective_message.reply_text(text)


# =========================
# FAQ
# =========================

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
❓ FAQ

━━━━━━━━━━━━━━━━━━━━

How to register?
Use /register

Where matches happen?
Inside Telegram

Entry Fee?
Check pinned message
"""

    await update.effective_message.reply_text(text)


# =========================
# COLESIUM / DPDL GROUP
# =========================

async def Colesium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Links and usernames
    dpdl_colesium_link = "https://t.me/DpdL_Gc"
    dpdl_dominion_link = "https://t.me/DPDL_HC"
    dpdl_colesium_username = "@DpdL_Gc"
    dpdl_dominion_username = "@DPDL_HC"

    text = f"""
📋 <b>JOIN THE DPDL HUBS</b>

━━━━━━━━━━━━━━━━━━━━

<blockquote>
🎯 <b>DPDL COLESIUM</b> – The primary hub for all tournament updates, discussions, and registrations.
</blockquote>

➡️ <a href="{dpdl_colesium_link}">{dpdl_colesium_username}</a>

<blockquote>
💬 Stay connected via <b>DPDL DOMINION</b> – official DPDL updates and announcements.
</blockquote>

➡️ <a href="{dpdl_dominion_link}">{dpdl_dominion_username}</a>

━━━━━━━━━━━━━━━━━━━━

<i>Join now and be part of the DPDL community!</i>
"""

    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

# =========================
# REGISTER
# =========================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()

    if not db["registration_status"]:
        await update.effective_message.reply_text(
f"🚫 <b>REGISTRATIONS CLOSED</b>\n\n🏏 {db['tournament_name']}\n\nRegistrations will open soon.",
            parse_mode=ParseMode.HTML
        )
        return

    user_id = update.effective_user.id
    db.setdefault("pending_registration", {})

    # If user is already in pending registration, restart from step 1
    db["pending_registration"][str(user_id)] = {"step": 1}
    save_db(db)

    await update.effective_message.reply_text(
        "📝 <b>TEAM REGISTRATION - STEP 1/3</b>\n\n"
        "Please send your <b>Team Name</b> 🏏:",
        parse_mode=ParseMode.HTML
    )


# =========================
# USER MESSAGE HANDLER (Updated for Step-by-Step Registration)
# =========================

async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    user = update.message.from_user
    user_id = str(user.id)
    text = update.message.text or ""
    db = load_db()

    # Initialize pending_registration if not exists
    db.setdefault("pending_registration", {})

    # Check if user is in pending registration
    if user_id in db["pending_registration"]:
        pending = db["pending_registration"][user_id]
        step = pending.get("step", 1)

        if step == 1:
            # Capture team name
            pending["team_name"] = text.strip()
            pending["step"] = 2
            save_db(db)
            await update.message.reply_text(
                "👤 <b>STEP 2/3</b>\n\nPlease send the <b>Captain Name</b> ✏️:",
                parse_mode=ParseMode.HTML
            )
            return

        elif step == 2:
            # Capture captain name
            pending["captain_name"] = text.strip()
            pending["step"] = 3
            save_db(db)
            await update.message.reply_text(
                "🔗 <b>STEP 3/3</b>\n\nPlease send the <b>Captain Username</b> (e.g., @username) 💬:",
                parse_mode=ParseMode.HTML
            )
            return

        elif step == 3:
            # Capture captain username and show confirmation
            username = text.strip()
            if not username.startswith("@"):
                await update.message.reply_text("❌ Invalid username format. It should start with @. Please try again:")
                return

            pending["username"] = username

            # Show confirmation summary
            summary = (
f"📋 <b>REGISTRATION SUMMARY</b>\n\n"
f"🏏 <b>Team Name:</b> {pending['team_name']}\n"
f"👤 <b>Captain Name:</b> {pending['captain_name']}\n"
f"💬 <b>Captain Username:</b> {pending['username']}\n\n"
"Please confirm your registration ✅ or edit ✏️"
            )

            keyboard = [
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_registration"),
                 InlineKeyboardButton("✏️ Edit", callback_data="edit_registration")]
            ]

            await update.message.reply_text(
                summary,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            pending["step"] = 4  # Waiting for confirmation
            save_db(db)
            return

    # If not in registration flow, treat as normal user message
    await handle_user_general_message(update, context, db)


# =========================
# CALLBACK HANDLER FOR CONFIRMATION
# =========================

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)
    db = load_db()

    # Handle registration confirmation
    if data == "confirm_registration":
        if user_id not in db["pending_registration"]:
            await query.edit_message_text("⚠️ Registration session expired. Please /register again.")
            return

        pending = db["pending_registration"].pop(user_id)
        db["captains"][user_id] = {
            "username": pending["username"],
            "data": f"🏏 {pending['team_name']}\n👤 {pending['captain_name']}\n💬 {pending['username']}"
        }
        save_db(db)

        await query.edit_message_text("✅ Registration successful! Welcome to the tournament 🏆")
        return

    elif data == "edit_registration":
        if user_id not in db["pending_registration"]:
            await query.edit_message_text("⚠️ Registration session expired. Please /register again.")
            return

        pending = db["pending_registration"][user_id]
        pending["step"] = 1  # Restart flow
        save_db(db)
        await query.edit_message_text("✏️ Registration restarted. Please send your Team Name 🏏:")
        return

    # Handle menu buttons
    elif data == "rules":
        await rules(update, context)
    elif data == "faq":
        await faq(update, context)
    elif data == "register":
        await register(update, context)


# =========================
# Helper function for general user messages outside registration
# =========================
async def handle_user_general_message(update, context, db):
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "NoUsername"
    text = update.message.text or ""

    header = f"""
📩 USER MESSAGE
👤 {user.first_name}
🔗 {username}
🆔 {user.id}
"""

    if update.message.text:
        sent = await context.bot.send_message(config.ADMIN_GROUP_ID, f"{header}\n{text}")
        db["message_map"][str(sent.message_id)] = user.id
        save_db(db)

# =========================
# ADMIN REPLY
# =========================

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.id != config.ADMIN_GROUP_ID:
        return

    if not is_admin(update.message.from_user.id):
        return

    if not update.message.reply_to_message:
        return

    db = load_db()

    replied = str(update.message.reply_to_message.message_id)

    if replied not in db["message_map"]:
        return

    user_id = db["message_map"][replied]

    if update.message.text:
        await context.bot.send_message(user_id, update.message.text)

    elif update.message.sticker:
        await context.bot.send_sticker(user_id, update.message.sticker.file_id)

    elif update.message.photo:
        await context.bot.send_photo(user_id, update.message.photo[-1].file_id)

    elif update.message.document:
        await context.bot.send_document(user_id, update.message.document.file_id)


# =========================
# ADMIN COMMANDS
# =========================

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.id != config.OWNER_ID:
        return

    uid = int(context.args[0])

    db = load_db()

    if uid not in db["admins"]:
        db["admins"].append(uid)
        save_db(db)

    await update.message.reply_text("Admin added.")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message.from_user.id != config.OWNER_ID:
        return

    uid = int(context.args[0])

    db = load_db()

    if uid in db["admins"]:
        db["admins"].remove(uid)
        save_db(db)

    await update.message.reply_text("Admin removed.")


async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):

    db = load_db()

    msg = "Admins:\n\n"

    for a in db["admins"]:
        msg += f"{a}\n"

    await update.message.reply_text(msg)


async def open_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.message.from_user.id):
        return

    db = load_db()

    db["registration_status"] = True
    save_db(db)

    await update.message.reply_text("Registrations opened.")


async def close_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.message.from_user.id):
        return

    db = load_db()

    db["registration_status"] = False
    save_db(db)

    await update.message.reply_text("Registrations closed.")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/broadcast Your message"
        )
        return

    msg = " ".join(context.args)

    db = load_db()

    sent = 0
    failed = 0

    for uid in db["users"]:

        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"""
📢 <b>Tournament Announcement</b>

{msg}
""",
                parse_mode=ParseMode.HTML
            )

            sent += 1

        except:
            failed += 1

    await update.message.reply_text(
        f"Broadcast complete.\n\nSent: {sent}\nFailed: {failed}"
    )

async def teams(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.message.from_user.id):
        return

    db = load_db()

    msg = "REGISTERED TEAMS\n\n"

    for uid, data in db["captains"].items():
        msg += f"{data['data']}\n\n"

    await update.message.reply_text(msg)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    db = load_db()

    teams = len(db["captains"])
    admins = len(db["admins"])

    await update.message.reply_text(
f"""
BOT STATS

Teams registered: {teams}
Admins: {admins}
"""
    )


# =========================
# MAIN
# =========================

def main():

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("faq", faq))
    app.add_handler(CommandHandler("Colesium", Colesium_cmd))

    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("admins", admins))

    app.add_handler(CommandHandler("openregistrations", open_reg))
    app.add_handler(CommandHandler("closeregistrations", close_reg))

    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("teams", teams))
    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(CallbackQueryHandler(menu_handler))

    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, user_message))
    app.add_handler(MessageHandler(filters.Chat(config.ADMIN_GROUP_ID) & filters.REPLY, admin_reply))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()