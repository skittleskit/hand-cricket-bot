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

DB_FILE = "database.json"


def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    data.setdefault("captains", {})               # uid -> { username, data }
    data.setdefault("message_map", {})            # admin message id -> user id
    data.setdefault("admins", [config.OWNER_ID])  # editable admins
    data.setdefault("registration_status", False)
    data.setdefault("tournament_name", "Dice Pe Destiny League")
    data.setdefault("users", [])                  # users who started bot (for broadcast)
    data.setdefault("pending_registration", {})   # user_id -> pending fields

    return data


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# =========================
# ADMIN CHECK (includes permanent admins from config)
# =========================

def is_admin(user_id: int) -> bool:
    db = load_db()
    perms = getattr(config, "PERMANENT_ADMINS", [])
    return (
        user_id == getattr(config, "OWNER_ID", None)
        or user_id in db.get("admins", [])
        or (isinstance(perms, list) and user_id in perms)
    )


# =========================
# UI: main menu + admin panel
# =========================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 Register Team", callback_data="register")],
        [
            InlineKeyboardButton("🏟 Colesium", url="https://t.me/DpdL_Gc"),
            InlineKeyboardButton("📜 Rules", callback_data="rules"),
        ],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_panel_markup():
    keyboard = [
        [
            InlineKeyboardButton("📋 Teams", callback_data="panel_teams_0"),
            InlineKeyboardButton("➕ Add Team", callback_data="panel_addteam"),
        ],
        [
            InlineKeyboardButton("🟢 Open Reg", callback_data="panel_openreg"),
            InlineKeyboardButton("🔴 Close Reg", callback_data="panel_closereg"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="panel_broadcast"),
            InlineKeyboardButton("📊 Stats", callback_data="panel_stats"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# =========================
# ADMIN PANEL COMMAND
# =========================

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /panel — show admin control panel"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    db = load_db()
    text = (
        f"⚙️ <b>ADMIN CONTROL PANEL</b>\n\n"
        f"🏏 Tournament: <b>{db['tournament_name']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏏 Teams Registered: <b>{len(db['captains'])}</b>\n\n"
        f"📝 Registrations: {'🟢 OPEN' if db['registration_status'] else '🔴 CLOSED'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Select an action below."
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_panel_markup())


# Compatibility helper: send admin panel as reply text to a chat id
async def _send_admin_panel_to_chat(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    text = (
        f"⚙️ <b>ADMIN CONTROL PANEL</b>\n\n"
        f"🏏 Tournament: <b>{db['tournament_name']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏏 Teams Registered: <b>{len(db['captains'])}</b>\n\n"
        f"📝 Registrations: {'🟢 OPEN' if db['registration_status'] else '🔴 CLOSED'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Select an action below."
    )
    await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=admin_panel_markup())


# =========================
# TEAM VIEW (paginated) helpers
# =========================

def _get_sorted_team_list(db):
    # Return list of (uid, data) tuples in deterministic order
    try:
        return sorted(db["captains"].items(), key=lambda kv: int(kv[0]))
    except Exception:
        # fallback to insertion order
        return list(db["captains"].items())


async def show_team_page(query, page_index: int):
    """Edit the callback message to show the team at page_index (0-based)."""
    db = load_db()
    teams = _get_sorted_team_list(db)

    if not teams:
        await query.edit_message_text("⚠️ No teams registered.")
        return

    # clamp page index
    if page_index < 0:
        page_index = 0
    if page_index >= len(teams):
        page_index = len(teams) - 1

    uid, data = teams[page_index]

    text = (
        f"📋 <b>TEAM {page_index+1} / {len(teams)}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{data['data']}\n\n"
        f"🆔 <code>{uid}</code>\n"
    )

    nav_row = []
    if page_index > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"panel_teams_{page_index-1}"))
    if page_index < len(teams) - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"panel_teams_{page_index+1}"))

    keyboard = [
        [InlineKeyboardButton("✏️ Edit", callback_data=f"editteam_{uid}"), InlineKeyboardButton("❌ Remove", callback_data=f"removeteam_{uid}")],
    ]
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🔙 Back Panel", callback_data="panel_back")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = update.effective_user.first_name or update.effective_user.username or "Player"
    user_id = update.effective_user.id

    if user_id not in db.get("users", []):
        db["users"].append(user_id)
        save_db(db)

    text = (
        f"<b>🏏 {db['tournament_name']}</b>\n"
        f"<u>Official tournament registration system</u>\n\n"
        f"<blockquote>Welcome, <b>{user}</b>.\nRegister your team and compete with the best.</blockquote>\n\n"
        f"<b>Features</b>\n• Team registration  \n• Tournament announcements  \n• Direct admin support  \n• Match coordination  \n\n"
        f"<blockquote><i>Use the menu below to continue.</i></blockquote>"
    )

    # send banner if exists, else text
    try:
        with open("banner.png", "rb") as photo:
            await update.message.reply_photo(photo=photo, caption=text, parse_mode=ParseMode.HTML, reply_markup=main_menu())
    except FileNotFoundError:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu())


# =========================
# CANCEL REGISTRATION
# =========================

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    if user_id in db.get("pending_registration", {}):
        db["pending_registration"].pop(user_id)
        save_db(db)
        await update.effective_message.reply_text("❌ Your registration has been cancelled.\nYou can start again anytime using /register.")
    else:
        await update.effective_message.reply_text("⚠️ You don't have any ongoing registration to cancel.")


# =========================
# CALLBACK / MENU HANDLER
# =========================

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """All inline button callbacks come here."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    user = query.from_user

    # Protect admin-only panel callbacks
    admin_only_prefixes = ("panel_", "removeteam_", "editteam_", "confirmremove_", "panel_back", "panel_addteam", "panel_openreg", "panel_closereg", "panel_stats", "panel_broadcast")
    if any(data.startswith(p) for p in admin_only_prefixes) and not is_admin(user.id):
        await query.answer("Unauthorized", show_alert=True)
        return

    db = load_db()

    # ===== PANEL NAV =====
    if data == "panel_back":
        # Show admin panel in place of callback message
        await query.edit_message_text(
            f"⚙️ <b>ADMIN CONTROL PANEL</b>\n\n"
            f"🏏 Tournament: <b>{db['tournament_name']}</b>\n\n"
            f"🏏 Teams Registered: <b>{len(db['captains'])}</b>\n\n"
            f"📝 Registrations: {'🟢 OPEN' if db['registration_status'] else '🔴 CLOSED'}",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_markup()
        )
        return

    if data.startswith("panel_teams_"):
        # show given page
        try:
            parts = data.split("_")
            page = int(parts[2])
        except Exception:
            page = 0
        await show_team_page(query, page)
        return

    if data == "panel_addteam":
        # set flow in context.user_data and prompt admin to send team details in same chat
        context.user_data["flow"] = "add_team"
        await query.edit_message_text(
            "➕ <b>ADD TEAM</b>\n\nSend team details in this chat in the format:\n\n<i>TEAM NAME | CAPTAIN NAME | @USERNAME</i>\n\nOr use /addteam command in the same chat.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="panel_back")]])
        )
        return

    if data.startswith("removeteam_"):
        uid = data.split("_", 1)[1]
        await query.edit_message_text(
            "⚠️ Are you sure you want to delete this team?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Delete", callback_data=f"confirmremove_{uid}"), InlineKeyboardButton("❌ Cancel", callback_data="panel_back")]
            ])
        )
        return

    if data.startswith("confirmremove_"):
        uid = data.split("_", 1)[1]
        if uid in db["captains"]:
            removed = db["captains"].pop(uid)
            save_db(db)
            await query.edit_message_text(f"❌ Team removed:\n\n{removed['data']}", parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text("⚠️ Team not found.", reply_markup=admin_panel_markup())
        return

    if data.startswith("editteam_"):
        uid = data.split("_", 1)[1]
        if uid not in db["captains"]:
            await query.edit_message_text("⚠️ Team not found.", reply_markup=admin_panel_markup())
            return
        # set context to edit mode and prompt admin to send new details
        context.user_data["flow"] = "edit_team"
        context.user_data["edit_uid"] = uid
        await query.edit_message_text(
            "✏️ <b>EDIT TEAM</b>\n\nSend updated details in this chat in format:\n\n<i>TEAM NAME | CAPTAIN NAME | @USERNAME</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="panel_back")]])
        )
        return

    if data == "panel_openreg":
        db["registration_status"] = True
        save_db(db)
        await query.answer("Registrations opened")
        # replace message with updated panel
        await query.edit_message_text(
            f"🟢 Registrations OPENED\n\nUse the panel below.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_markup()
        )
        return

    if data == "panel_closereg":
        db["registration_status"] = False
        save_db(db)
        await query.answer("Registrations closed")
        await query.edit_message_text(
            f"🔴 Registrations CLOSED\n\nUse the panel below.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_markup()
        )
        return

    if data == "panel_stats":
        text = (
            f"📊 <b>BOT STATISTICS</b>\n\n"
            f"👥 Users: {len(db['users'])}\n"
            f"🏏 Teams: {len(db['captains'])}\n"
            f"👮 Admins: {len(db['admins'])}\n"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_panel_markup())
        return

    if data == "panel_broadcast":
        # set flow to broadcast
        context.user_data["flow"] = "panel_broadcast"
        await query.edit_message_text("📢 <b>BROADCAST</b>\n\nSend the announcement message to broadcast to all users.", parse_mode=ParseMode.HTML)
        return

    # --- fallback for other callback usages (rules, faq, register etc.) ---
    if data == "rules":
        # reply to same chat with rules (do not edit panel message)
        text = "📜 TOURNAMENT RULEBOOK\n\nTo be Announced Soon!"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if data == "faq":
        text = (
            "❓ FAQ\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "How to register? Use /register\n"
            "Squad size? 14 Players\n"
            "Where matches happen? DPDL Coliseum\n"
            "Prize? Tentative"
        )
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if data == "register":
        # If pressed within private chat, start registration in that chat
        if query.message.chat.type == ChatType.PRIVATE:
            # start registration
            db["pending_registration"][str(query.from_user.id)] = {"step": 1}
            save_db(db)
            await query.message.reply_text("📝 <b>TEAM REGISTRATION - STEP 1/3</b>\n\nSend your <b>Team Name</b> 🏏:", parse_mode=ParseMode.HTML)
            return
        else:
            # show DM button
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Register in DM", url=f"https://t.me/{context.bot.username}?start=register")]])
            await query.message.reply_text("Registration must be completed in the private chat! ⬇️", reply_markup=keyboard)
            return

    # unknown callback_data
    await query.answer()


# =========================
# RULES / FAQ / COLESIUM
# =========================

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📜 TOURNAMENT RULEBOOK\n<u>To be Announced Soon!</u>"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ FAQ\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "How to register? Use /register\n"
        "Squad size? 14 Players\n"
        "Where matches happen? DPDL Coliseum\n"
        "Prize? Tentative"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def Colesium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 <b>JOIN THE DPDL HUBS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        '➡️ <a href="https://t.me/DpdL_Gc">@DpdL_Gc</a>\n'
        '➡️ <a href="https://t.me/DPDL_HC">@DPDL_HC</a>\n'
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


# =========================
# REGISTER (starts DM flow if used in group)
# =========================

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user_id = str(update.effective_user.id)

    if not db["registration_status"]:
        await update.effective_message.reply_text(f"🚫<b>REGISTRATIONS CLOSED</b>\n\n🏏 {db['tournament_name']}", parse_mode=ParseMode.HTML)
        return

    # If not private, send DM link
    if update.effective_chat.type != ChatType.PRIVATE:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Register in DM", url=f"https://t.me/{context.bot.username}?start=register")]])
        await update.effective_message.reply_text("Registration must be completed in the private chat! ⬇️", reply_markup=keyboard)
        return

    # Private chat: start step-by-step registration
    db["pending_registration"][user_id] = {"step": 1}
    save_db(db)
    await update.effective_message.reply_text("📝 <b>TEAM REGISTRATION - STEP 1/3</b>\n\nSend your <b>Team Name</b> 🏏:", parse_mode=ParseMode.HTML)


# =========================
# MESSAGE HANDLER (private chats only)
# Handles: registration steps, admin add/edit flows, broadcasts from panel
# =========================

async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    db = load_db()
    user = update.message.from_user
    user_id = str(user.id)
    text = (update.message.text or "").strip()

    # ----- Admin flows (add team / edit team / broadcast from panel) -----
    if is_admin(user.id) and context.user_data.get("flow"):
        flow = context.user_data.get("flow")

        # Add team (via panel inline -> admin sends details here)
        if flow == "add_team":
            # expected: TEAM | CAPTAIN | @username
            if "|" not in text:
                await update.message.reply_text("Invalid format. Use:\nTEAM NAME | CAPTAIN NAME | @USERNAME")
                return
            team, captain, username = [x.strip() for x in text.split("|", 2)]
            if not username.startswith("@"):
                await update.message.reply_text("Username should start with @. Please try again.")
                return

            uid = _generate_new_team_uid(db)
            db["captains"][uid] = {"username": username, "data": f"🏏 {team}\n👤 {captain}\n💬 {username}"}
            save_db(db)
            context.user_data.pop("flow", None)
            await update.message.reply_text(f"✅ Team added (UID: {uid}).", parse_mode=ParseMode.HTML)
            return

        # Edit team
        if flow == "edit_team":
            uid = context.user_data.get("edit_uid")
            if not uid:
                context.user_data.pop("flow", None)
                await update.message.reply_text("Edit session expired. Try again from panel.")
                return
            if "|" not in text:
                await update.message.reply_text("Invalid format. Use:\nTEAM NAME | CAPTAIN NAME | @USERNAME")
                return
            team, captain, username = [x.strip() for x in text.split("|", 2)]
            if not username.startswith("@"):
                await update.message.reply_text("Username should start with @. Please try again.")
                return
            db["captains"][uid] = {"username": username, "data": f"🏏 {team}\n👤 {captain}\n💬 {username}"}
            save_db(db)
            context.user_data.pop("flow", None)
            context.user_data.pop("edit_uid", None)
            await update.message.reply_text("✅ Team updated.")
            return

        # Panel broadcast
        if flow == "panel_broadcast":
            # send broadcast to db["users"]
            msg = text
            sent = failed = 0
            for uid in db.get("users", []):
                try:
                    await context.bot.send_message(uid, f"📢 <b>Tournament Announcement</b>\n\n{msg}", parse_mode=ParseMode.HTML)
                    sent += 1
                except Exception:
                    failed += 1
            context.user_data.pop("flow", None)
            await update.message.reply_text(f"Broadcast complete.\nSent: {sent}\nFailed: {failed}")
            return

    # ----- Registration flow for normal users -----
    if user_id in db.get("pending_registration", {}):
        pending = db["pending_registration"][user_id]
        step = pending.get("step", 1)

        if step == 1:
            pending["team_name"] = text
            pending["step"] = 2
            save_db(db)
            await update.message.reply_text("👤 <b>STEP 2/3</b>\n\nSend the <b>Captain Name</b>:", parse_mode=ParseMode.HTML)
            return

        if step == 2:
            pending["captain_name"] = text
            pending["step"] = 3
            save_db(db)
            await update.message.reply_text("🔗 <b>STEP 3/3</b>\n\nSend the <b>Captain Username</b> (format: @username):", parse_mode=ParseMode.HTML)
            return

        if step == 3:
            username = text
            if not username.startswith("@"):
                await update.message.reply_text("❌ Invalid username format. It should start with @. Please try again:")
                return
            pending["username"] = username
            # show summary with confirm/edit buttons
            summary = (
                f"📋 <b>REGISTRATION SUMMARY</b>\n\n"
                f"🏏 <b>Team Name:</b> {pending['team_name']}\n"
                f"👤 <b>Captain Name:</b> {pending['captain_name']}\n"
                f"💬 <b>Captain Username:</b> {pending['username']}\n\n"
                "Please confirm your registration ✅ or edit ✏️"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="confirm_registration"), InlineKeyboardButton("✏️ Edit", callback_data="edit_registration")]
            ])
            await update.message.reply_text(summary, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

    # ----- General messages from users: forward to admin group -----
    await handle_user_general_message(update, context, db)


# small helper to generate new UID
def _generate_new_team_uid(db):
    if not db["captains"]:
        return "1001"
    try:
        current_max = max(int(k) for k in db["captains"].keys() if str(k).isdigit())
        return str(current_max + 1)
    except Exception:
        # fallback
        existing = [int(k) for k in db["captains"].keys() if k.isdigit()]
        if not existing:
            return "1001"
        return str(max(existing) + 1)


# =========================
# FORWARD USER MESSAGES TO ADMIN
# =========================

async def handle_user_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db=None):
    db = db if db is not None else load_db()
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "NoUsername"
    header = f"📩 USER MESSAGE\n👤 {user.first_name}\n🔗 {username}\n🆔 {user.id}"

    sent_msg = None
    try:
        if update.message.text:
            sent_msg = await context.bot.send_message(config.ADMIN_GROUP_ID, f"{header}\n\n{update.message.text}")
        elif update.message.sticker:
            sent_msg = await context.bot.send_message(config.ADMIN_GROUP_ID, header)
            await context.bot.send_sticker(config.ADMIN_GROUP_ID, update.message.sticker.file_id)
        elif update.message.photo:
            caption = update.message.caption or ""
            sent_msg = await context.bot.send_photo(config.ADMIN_GROUP_ID, update.message.photo[-1].file_id, caption=f"{header}\n\n{caption}" if caption else header)
        elif update.message.document:
            caption = update.message.caption or ""
            sent_msg = await context.bot.send_document(config.ADMIN_GROUP_ID, update.message.document.file_id, caption=f"{header}\n\n{caption}" if caption else header)
    except Exception:
        sent_msg = None

    if sent_msg:
        db.setdefault("message_map", {})
        db["message_map"][str(sent_msg.message_id)] = user.id
        save_db(db)


# =========================
# ADMIN REPLY (reply to forwarded admin message in admin group)
# =========================

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != config.ADMIN_GROUP_ID:
        return
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


# =========================
# ADMIN COMMANDS (addteam exists too)
# =========================

async def addteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args or [])
    if "|" not in text:
        await update.message.reply_text("Usage:\n/addteam TEAM | CAPTAIN | @USERNAME")
        return
    team, captain, username = [x.strip() for x in text.split("|", 2)]
    if not username.startswith("@"):
        await update.message.reply_text("Username must start with @")
        return
    db = load_db()
    uid = _generate_new_team_uid(db)
    db["captains"][uid] = {"username": username, "data": f"🏏 {team}\n👤 {captain}\n💬 {username}"}
    save_db(db)
    await update.message.reply_text(f"✅ Team added (UID: {uid}).")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != getattr(config, "OWNER_ID", None):
        return
    if not context.args:
        return
    uid = int(context.args[0])
    db = load_db()
    if uid not in db["admins"]:
        db["admins"].append(uid)
        save_db(db)
    await update.message.reply_text("Admin added.")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != getattr(config, "OWNER_ID", None):
        return
    if not context.args:
        return
    uid = int(context.args[0])
    db = load_db()
    if uid in db["admins"]:
        db["admins"].remove(uid)
        save_db(db)
    await update.message.reply_text("Admin removed.")


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    for uid in db.get("users", []):
        try:
            await context.bot.send_message(uid, f"📢 <b>Tournament Announcement</b>\n\n{msg}", parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"Broadcast complete.\nSent: {sent}\nFailed: {failed}")


async def teams_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    db = load_db()
    if not db["captains"]:
        await update.message.reply_text("No teams registered.")
        return
    lines = []
    for uid, v in _get_sorted_team_list(db):
        lines.append(f"{v['data']}\n🆔 {uid}")
    await update.message.reply_text("\n\n".join(lines))


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    await update.message.reply_text(f"BOT STATS\n\nTeams registered: {len(db['captains'])}\nAdmins: {len(db['admins'])}")


# =========================
# MAIN
# =========================

def main():
    app = Application.builder().token(config.BOT_TOKEN).build()

    # user commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("faq", faq))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("cancel", cancel_registration))
    app.add_handler(CommandHandler("Colesium", Colesium_cmd))

    # admin utility commands
    app.add_handler(CommandHandler("addteam", addteam))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("admins", admins_cmd))
    app.add_handler(CommandHandler("openregistrations", open_reg))
    app.add_handler(CommandHandler("closeregistrations", close_reg))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("teams", teams_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))

    # callbacks & messages
    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, user_message))
    app.add_handler(MessageHandler(filters.Chat(config.ADMIN_GROUP_ID) & filters.REPLY, admin_reply))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()