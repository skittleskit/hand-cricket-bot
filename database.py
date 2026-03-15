# database.py
import os
import json
from typing import Dict, Any, Optional
import psycopg2
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL")
POOL: Optional[SimpleConnectionPool] = None
LOCAL_JSON = "database.json"  # optional import on first init


def get_conn():
    """Acquire a connection from the pool. Remember to put it back with putconn."""
    global POOL
    if POOL is None:
        raise RuntimeError("DB pool not initialized. Call init_db() first.")
    return POOL.getconn()


def put_conn(conn):
    global POOL
    if POOL:
        POOL.putconn(conn)


def init_db():
    """
    Initialize connection pool and create tables if they don't exist.
    If local database.json exists and DB is empty, import it (one-time).
    """
    global POOL
    if DATABASE_URL is None:
        raise RuntimeError("Please set DATABASE_URL environment variable.")

    # create a small pool
    POOL = SimpleConnectionPool(minconn=1, maxconn=8, dsn=DATABASE_URL)

    conn = get_conn()
    try:
        cur = conn.cursor()
        # Create tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS captains (
            uid TEXT PRIMARY KEY,
            username TEXT,
            data TEXT
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id BIGINT PRIMARY KEY
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_registration (
            user_id TEXT PRIMARY KEY,
            step INTEGER,
            team_name TEXT,
            captain_name TEXT,
            username TEXT
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS message_map (
            admin_message_id TEXT PRIMARY KEY,
            user_id BIGINT
        );
        """)
        conn.commit()

        # ensure some default settings exist
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                    ("registration_status", "false"))
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                    ("tournament_name", "Dice Pe Destiny League"))
        conn.commit()

        # If tables empty and local JSON exists -> populate DB from it (safe import)
        cur.execute("SELECT COUNT(*) FROM captains")
        count = cur.fetchone()[0]
        if count == 0 and os.path.exists(LOCAL_JSON):
            try:
                with open(LOCAL_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # import captains
                for uid, t in data.get("captains", {}).items():
                    cur.execute("INSERT INTO captains (uid, username, data) VALUES (%s, %s, %s) ON CONFLICT (uid) DO NOTHING",
                                (str(uid), t.get("username"), t.get("data")))
                # import admins
                for a in data.get("admins", []):
                    cur.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (int(a),))
                # import users
                for u in data.get("users", []):
                    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (int(u),))
                # import message_map
                for mid, uid in data.get("message_map", {}).items():
                    try:
                        cur.execute("INSERT INTO message_map (admin_message_id, user_id) VALUES (%s, %s) ON CONFLICT (admin_message_id) DO NOTHING",
                                    (str(mid), int(uid)))
                    except Exception:
                        pass
                # import pending registration
                for uid, pending in data.get("pending_registration", {}).items():
                    cur.execute("""
                        INSERT INTO pending_registration (user_id, step, team_name, captain_name, username)
                        VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_id) DO NOTHING
                    """, (str(uid), pending.get("step", 1), pending.get("team_name"), pending.get("captain_name"), pending.get("username")))
                # import settings
                if "registration_status" in data:
                    cur.execute("UPDATE settings SET value=%s WHERE key='registration_status'", ("true" if data["registration_status"] else "false",))
                if "tournament_name" in data:
                    cur.execute("UPDATE settings SET value=%s WHERE key='tournament_name'", (data["tournament_name"],))
                conn.commit()
            except Exception:
                conn.rollback()
        cur.close()
    finally:
        put_conn(conn)


def _row_to_bool(val: Optional[str]) -> bool:
    return str(val).lower() in ("1", "true", "t", "yes", "y")


def load_db() -> Dict[str, Any]:
    """
    Return a dict with the same structure your old load_db() returned, built from Postgres.
    {
      "captains": { uid: { "username":..., "data":... } , ... },
      "message_map": { admin_msg_id: user_id, ... },
      "admins": [int,...],
      "registration_status": bool,
      "tournament_name": str,
      "users": [int,...],
      "pending_registration": { user_id: {step:..., team_name:..., captain_name:..., username:...}, ... }
    }
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        db = {}
        # captains
        cur.execute("SELECT uid, username, data FROM captains")
        captains = {}
        for uid, username, data in cur.fetchall():
            captains[str(uid)] = {"username": username, "data": data}
        db["captains"] = captains

        # message_map
        cur.execute("SELECT admin_message_id, user_id FROM message_map")
        msgmap = {}
        for mid, uid in cur.fetchall():
            msgmap[str(mid)] = int(uid)
        db["message_map"] = msgmap

        # admins
        cur.execute("SELECT user_id FROM admins")
        db["admins"] = [int(r[0]) for r in cur.fetchall()]

        # users
        cur.execute("SELECT user_id FROM users")
        db["users"] = [int(r[0]) for r in cur.fetchall()]

        # pending_registration
        cur.execute("SELECT user_id, step, team_name, captain_name, username FROM pending_registration")
        pending = {}
        for user_id, step, team_name, captain_name, username in cur.fetchall():
            pending[str(user_id)] = {
                "step": int(step) if step is not None else 1,
                "team_name": team_name,
                "captain_name": captain_name,
                "username": username
            }
        db["pending_registration"] = pending

        # settings
        cur.execute("SELECT key, value FROM settings")
        settings = {k: v for k, v in cur.fetchall()}
        db["registration_status"] = _row_to_bool(settings.get("registration_status", "false"))
        db["tournament_name"] = settings.get("tournament_name", "Dice Pe Destiny League")

        cur.close()
        return db
    finally:
        put_conn(conn)


def save_db(db: Dict[str, Any]):
    """
    Save the entire DB dictionary into Postgres.
    This function replaces table contents with the provided dict (simple and reliable).
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Replace captains: clear & insert
        cur.execute("TRUNCATE captains")
        for uid, v in db.get("captains", {}).items():
            cur.execute("INSERT INTO captains (uid, username, data) VALUES (%s, %s, %s) ON CONFLICT (uid) DO UPDATE SET username=EXCLUDED.username, data=EXCLUDED.data",
                        (str(uid), v.get("username"), v.get("data")))

        # Replace message_map
        cur.execute("TRUNCATE message_map")
        for mid, uid in db.get("message_map", {}).items():
            cur.execute("INSERT INTO message_map (admin_message_id, user_id) VALUES (%s, %s) ON CONFLICT (admin_message_id) DO UPDATE SET user_id=EXCLUDED.user_id",
                        (str(mid), int(uid)))

        # Replace admins
        cur.execute("TRUNCATE admins")
        for a in db.get("admins", []):
            cur.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (int(a),))

        # Replace users
        cur.execute("TRUNCATE users")
        for u in db.get("users", []):
            cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (int(u),))

        # Replace pending_registration
        cur.execute("TRUNCATE pending_registration")
        for uid, p in db.get("pending_registration", {}).items():
            cur.execute("""
                INSERT INTO pending_registration (user_id, step, team_name, captain_name, username)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (user_id) DO UPDATE
                SET step=EXCLUDED.step, team_name=EXCLUDED.team_name, captain_name=EXCLUDED.captain_name, username=EXCLUDED.username
            """, (str(uid), int(p.get("step", 1)), p.get("team_name"), p.get("captain_name"), p.get("username")))

        # Settings
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    ("registration_status", "true" if db.get("registration_status") else "false"))
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    ("tournament_name", db.get("tournament_name", "Dice Pe Destiny League")))

        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)