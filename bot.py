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
    data.setdefault("pending_registration", {})

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
        [InlineKeyboardButton("📝 Register Team", callback_data="register")],
        [
            InlineKeyboardButton("🖇️ Colesium", url="https://t.me/DpdL_Gc"),
            InlineKeyboardButton("📜 Rules", callback_data="rules")
        ],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")]
    ]
    return InlineKeyboardMarkup(keyboard)

# =========================
# ADMIN PANEL UI
# =========================

def admin_panel():
    keyboard = [
        [
            InlineKeyboardButton("📋 Teams", callback_data="panel_teams"),
            InlineKeyboardButton("➕ Add Team", callback_data="panel_addteam")
        ],
        [
            InlineKeyboardButton("🟢 Open Reg", callback_data="panel_openreg"),
            InlineKeyboardButton("🔴 Close Reg", callback_data="panel_closereg")
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="panel_broadcast"),
            InlineKeyboardButton("📊 Stats", callback_data="panel_stats")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    db = load_db()

    text = f"""
⚙️ <b>ADMIN CONTROL PANEL</b>

🏏 Tournament: <b>{db['tournament_name']}</b>

Teams Registered: <b>{len(db['captains'])}</b>
Registrations: {"🟢 OPEN" if db["registration_status"] else "🔴 CLOSED"}

Select an action below.
"""

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel()
    )

async def teams(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.message.from_user.id):
        return

    db = load_db()

    if not db["captains"]:
        await update.message.reply_text("No teams registered.")
        return

    for uid, data in db["captains"].items():

        keyboard = [[
            InlineKeyboardButton("✏️ Edit", callback_data=f"editteam_{uid}"),
            InlineKeyboardButton("❌ Remove", callback_data=f"removeteam_{uid}")
        ]]

        await update.message.reply_text(
            f"{data['data']}\n\n🆔 <code>{uid}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = update.effective_user.first_name
    user_id = update.effective_user.id

    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

    text = f"""
<b>🏏 {db['tournament_name']}</b>
<u>Official tournament registration system</u>
<blockquote>
Welcome, <b>{user}</b>.
Register your team and compete with the strongest players in the league.
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
# CANCEL REGISTRATION
# =========================

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()

    if user_id in db.get("pending_registration", {}):
        db["pending_registration"].pop(user_id)
        save_db(db)
        await update.effective_message.reply_text(
            "❌ Your registration has been cancelled.\nYou can start again anytime using /register."
        )
    else:
        await update.effective_message.reply_text(
            "⚠️ You don't have any ongoing registration to cancel."
        )

# =========================
# MENU HANDLER
# =========================

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)
    db = load_db()

    # --- Registration Confirmation ---
    if data == "confirm_registration":
        if user_id not in db.get("pending_registration", {}):
            await query.edit_message_text("⚠️ Registration session expired. Please /register again.")
            return

        pending = db["pending_registration"].pop(user_id)
        db["captains"][user_id] = {
            "username": pending["username"],
            "data": f"🏏 {pending['team_name']}\n👤 {pending['captain_name']}\n💬 {pending['username']}"
        }
        save_db(db)

        summary_text = (
            f"📝 <b>NEW TEAM REGISTRATION</b>\n\n"
            f"🏏 <b>Team Name:</b> {pending['team_name']}\n"
            f"👤 <b>Captain Name:</b> {pending['captain_name']}\n"
            f"💬 <b>Captain Username:</b> {pending['username']}\n"
            f"🆔 <b>User ID:</b> {user_id}"
        )

        sent_msg = await context.bot.send_message(
            chat_id=config.ADMIN_GROUP_ID,
            text=summary_text,
            parse_mode=ParseMode.HTML
        )

        db["message_map"][str(sent_msg.message_id)] = int(user_id)
        save_db(db)
        await query.edit_message_text("✅ Registration successful! Kindly subscribe @DPDL_HC for Updates.")
        return

    # --- Registration Edit ---
    elif data == "edit_registration":
        if user_id not in db.get("pending_registration", {}):
            await query.edit_message_text("⚠️ Registration session expired. Please /register again.")
            return
        pending = db["pending_registration"][user_id]
        pending["step"] = 1
        save_db(db)
        await query.edit_message_text("✏️ Registration restarted. Please send your Team Name 🏏:")
        return

    # --- Menu Buttons ---
    elif data == "rules":
        await rules(update, context)
    elif data == "faq":
        await faq(update, context)
    elif data == "register":
        await register(update, context)
        # =========================
    # ADMIN PANEL BUTTONS
    # =========================

    elif data == "panel_teams":

        db = load_db()

        if not db["captains"]:
            await query.edit_message_text("No teams registered.")
            return

        await query.edit_message_text("📋 Registered Teams:")

        for uid, data in db["captains"].items():

            keyboard = [[
                InlineKeyboardButton("✏️ Edit", callback_data=f"editteam_{uid}"),
                InlineKeyboardButton("❌ Remove", callback_data=f"removeteam_{uid}")
            ]]

            await context.bot.send_message(
                query.message.chat_id,
                f"{data['data']}\n\n🆔 <code>{uid}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


    elif data == "panel_openreg":

        db = load_db()
        db["registration_status"] = True
        save_db(db)

        await query.edit_message_text("🟢 Registrations OPENED", reply_markup=admin_panel())


    elif data == "panel_closereg":

        db = load_db()
        db["registration_status"] = False
        save_db(db)

        await query.edit_message_text("🔴 Registrations CLOSED", reply_markup=admin_panel())


    elif data == "panel_stats":

        db = load_db()

        text = f"""
📊 <b>BOT STATISTICS</b>

👥 Users: {len(db['users'])}
🏏 Teams: {len(db['captains'])}
👮 Admins: {len(db['admins'])}
"""

        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_panel())

    elif data.startswith("removeteam_"):

        uid = data.split("_")[1]

        db = load_db()

        if uid not in db["captains"]:
            await query.answer("Team not found", show_alert=True)
            return

        team = db["captains"].pop(uid)
        save_db(db)

        await query.edit_message_text(
            f"❌ Team Removed\n\n{team['data']}"
        )

# =========================
# RULES / FAQ / COLESIUM
# =========================

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📜 TOURNAMENT RULEBOOK
<u>To be Announced Soon!</u>
"""
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """❓ FAQ
━━━━━━━━━━━━━━━━━━━━
How to register? <blockquote>Use /register</blockquote>
Squad size? <blockquote>14 Players</blockquote>
Where matches happen? <blockquote>DPDL Coliseum</blockquote>
Prize? <blockquote>Tentative but no commitments</blockquote>
"""
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def Colesium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
📋 <b>JOIN THE DPDL HUBS</b>
━━━━━━━━━━━━━━━━━━━━
➡️ <a href="https://t.me/DpdL_Gc">@DpdL_Gc</a>
➡️ <a href="https://t.me/DPDL_HC">@DPDL_HC</a>
"""
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

# =========================
# REGISTER
# =========================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)

    if not db["registration_status"]:
        await update.effective_message.reply_text(
            f"🚫<b>REGISTRATIONS CLOSED</b>\n\n🏏 {db['tournament_name']}", parse_mode=ParseMode.HTML
        )
        return

    if update.effective_chat.type == ChatType.PRIVATE:
        # Direct DM registration
        db["pending_registration"][user_id] = {"step": 1}
        save_db(db)
        await update.effective_message.reply_text(
            "📝 <b>TEAM REGISTRATION - STEP 1/3</b>\n\n"
            "Welcome to the tournament! Let's start by setting up your team.\n\n"
            "🏏 <b>Team Name:</b>\nSend the name your team will compete with.",
            parse_mode=ParseMode.HTML
        )
    else:
        # In group → show button to start in DM
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩Register", url=f"t.me/{context.bot.username}?start=register")]
        ])
        await update.effective_message.reply_text(
            "Registration must be completed in the private chat! ⬇️",
            reply_markup=keyboard
        )
# =========================
# USER MESSAGE HANDLER
# =========================

async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    user = update.message.from_user
    user_id = str(user.id)
    text = update.message.text or ""
    db = load_db()

    # -----------------------------
    # Step-by-Step Registration
    # -----------------------------
    if user_id in db["pending_registration"]:
        pending = db["pending_registration"][user_id]
        step = pending.get("step", 1)

        if step == 1:
            pending["team_name"] = text.strip()
            pending["step"] = 2
            save_db(db)
            await update.message.reply_text(
                "👤 <b>STEP 2/3</b>\n\n"
                "Great! Now, tell us who will lead your team.\n\n"
                "🧢 <b>Captain Name:</b>\nSend the full name of your team captain.", parse_mode=ParseMode.HTML
            )
            return
        elif step == 2:
            pending["captain_name"] = text.strip()
            pending["step"] = 3
            save_db(db)
            await update.message.reply_text(
                "🔗 <b>STEP 3/3</b>\n\n"
                "Almost done! We need your Telegram handle for contact and updates.\n\n"
                "💬 <b>Captain Username:</b>\nSend it in format @username", parse_mode=ParseMode.HTML
            )
            return
        elif step == 3:
            username = text.strip()
            if not username.startswith("@"):
                await update.message.reply_text(
                    "❌ Invalid username format. It should start with @. Please try again:"
                )
                return
            pending["username"] = username
            pending["step"] = 4
            save_db(db)

            summary = (
f"📋 <b>REGISTRATION SUMMARY</b>\n\n"
f"🏏 <b>Team Name:</b> {pending['team_name']}\n"
f"👤 <b>Captain Name:</b> {pending['captain_name']}\n"
f"💬 <b>Captain Username:</b> {pending['username']}\n\n"
"Please confirm your registration ✅ or edit ✏️"
            )
            keyboard = [[
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_registration"),
                InlineKeyboardButton("✏️ Edit", callback_data="edit_registration")
            ]]
            await update.message.reply_text(summary, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            return

    # -----------------------------
    # General messages → Admin
    # -----------------------------
    await handle_user_general_message(update, context, db)

    # =========================
    # ADMIN TEAM EDIT
    # =========================

    if "edit_team" in context.user_data:

        uid = context.user_data.pop("edit_team")

        parts = text.split("|")

        if len(parts) != 3:
            await update.message.reply_text("Invalid format.\nUse:\nTEAM | CAPTAIN | @USERNAME")
            return

        team, captain, username = [x.strip() for x in parts]

        db["captains"][uid] = {
            "username": username,
            "data": f"🏏 {team}\n👤 {captain}\n💬 {username}"
        }

        save_db(db)

        await update.message.reply_text("✅ Team updated.")
        return

# =========================
# FORWARD USER MESSAGES TO ADMIN
# =========================

async def handle_user_general_message(update, context, db):
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "NoUsername"
    header = f"📩 USER MESSAGE\n👤 {user.first_name}\n🔗 {username}\n🆔 {user.id}"

    sent_msg = None

    if update.message.text:
        sent_msg = await context.bot.send_message(config.ADMIN_GROUP_ID, f"{header}\n\n{update.message.text}")
    elif update.message.sticker:
        sent_msg = await context.bot.send_message(config.ADMIN_GROUP_ID, header)
        await context.bot.send_sticker(config.ADMIN_GROUP_ID, update.message.sticker.file_id)
    elif update.message.photo:
        caption = update.message.caption or ""
        sent_msg = await context.bot.send_photo(
            config.ADMIN_GROUP_ID,
            update.message.photo[-1].file_id,
            caption=f"{header}\n\n{caption}" if caption else header
        )
    elif update.message.document:
        caption = update.message.caption or ""
        sent_msg = await context.bot.send_document(
            config.ADMIN_GROUP_ID,
            update.message.document.file_id,
            caption=f"{header}\n\n{caption}" if caption else header
        )

    if sent_msg:
        db.setdefault("message_map", {})
        db["message_map"][str(sent_msg.message_id)] = user.id
        save_db(db)

# =========================
# ADMIN REPLY
# =========================

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != config.ADMIN_GROUP_ID:
        return
    def is_admin(user_id):
        db = load_db()
        return user_id in db.get("admins", []) or user_id in config.PERMANENT_ADMINS
    if not update.message.reply_to_message:
        return

    db = load_db()
    replied = str(update.message.reply_to_message.message_id)
    if replied not in db.get("message_map", {}):
        return

    user_id = db["message_map"][replied]

    if update.message.text:
        await context.bot.send_message(user_id, update.message.text)
    elif update.message.sticker:
        await context.bot.send_sticker(user_id, update.message.sticker.file_id)
    elif update.message.photo:
        caption = update.message.caption or ""
        await context.bot.send_photo(user_id, update.message.photo[-1].file_id, caption=caption)
    elif update.message.document:
        caption = update.message.caption or ""
        await context.bot.send_document(user_id, update.message.document.file_id, caption=caption)

async def addteam(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    text = " ".join(context.args)

    if "|" not in text:
        await update.message.reply_text("Usage:\n/addteam TEAM | CAPTAIN | @USERNAME")
        return

    team, captain, username = [x.strip() for x in text.split("|")]

    db = load_db()

    uid = str(max([int(x) for x in db["captains"].keys()] + [1000]) + 1)

    db["captains"][uid] = {
        "username": username,
        "data": f"🏏 {team}\n👤 {captain}\n💬 {username}"
    }

    save_db(db)

    await update.message.reply_text("✅ Team added manually.")

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
    msg = "Admins:\n\n" + "\n".join(str(a) for a in db["admins"])
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
        await update.message.reply_text("Usage:\n/broadcast Your message")
        return
    msg = " ".join(context.args)
    db = load_db()
    sent = failed = 0
    for uid in db["users"]:
        try:
            await context.bot.send_message(uid, f"📢 <b>Tournament Announcement</b>\n\n{msg}", parse_mode=ParseMode.HTML)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"Broadcast complete.\nSent: {sent}\nFailed: {failed}")

async def teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    db = load_db()
    msg = "REGISTERED TEAMS\n\n" + "\n\n".join([v["data"] for v in db["captains"].values()])
    await update.message.reply_text(msg)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    await update.message.reply_text(f"BOT STATS\n\nTeams registered: {len(db['captains'])}\nAdmins: {len(db['admins'])}")

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
    app.add_handler(CommandHandler("cancel", cancel_registration))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("addteam", addteam))

    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, user_message))
    app.add_handler(MessageHandler(filters.Chat(config.ADMIN_GROUP_ID) & filters.REPLY, admin_reply))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()