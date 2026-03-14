import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))

# Permanent admins (won't reset on bot restart)
PERMANENT_ADMINS = [
    1250625181,  # Replace with actual Telegram user IDs
    5894972318,
    8494112180,
    6741775606,
]