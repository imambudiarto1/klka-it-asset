import sqlite3
import datetime
import os

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "asset.db")
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_tag       TEXT UNIQUE,
                asset_name      TEXT,
                category        TEXT,
                brand           TEXT,
                model           TEXT,
                serial_number   TEXT,
                status          TEXT DEFAULT 'Active',
                location        TEXT,
                department      TEXT,
                assigned_to     TEXT,
                assigned_email  TEXT,
                purchase_date   TEXT,
                warranty_expiry TEXT,
                notes           TEXT,
                created_at      TEXT,
                updated_at      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT,
                email         TEXT UNIQUE,
                password_hash TEXT,
                role          TEXT,
                created_at    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id   INTEGER,
                action     TEXT,
                detail     TEXT,
                changed_by TEXT,
                changed_at TEXT
            )
        """)
        conn.commit()


def get_all_assets(search="", category="", status="", department=""):
    q = "SELECT * FROM assets WHERE 1=1"
    params = []
    if search:
        q += " AND (asset_name LIKE ? OR asset_tag LIKE ? OR serial_number LIKE ? OR assigned_to LIKE ? OR brand LIKE ?)"
        s = f"%{search}%"
        params += [s, s, s, s, s]
    if category:
        q += " AND category = ?"
        params.append(category)
    if status:
        q += " AND status = ?"
        params.append(status)
    if department:
        q += " AND department = ?"
        params.append(department)
    q += " ORDER BY category, asset_name"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_asset_by_id(aid):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
        return dict(row) if row else None


def create_asset(data: dict) -> int:
    cols = ", ".join(data.keys())
    ph   = ", ".join(["?"] * len(data))
    with get_conn() as conn:
        cur = conn.execute(f"INSERT INTO assets ({cols}) VALUES ({ph})", list(data.values()))
        conn.commit()
        return cur.lastrowid


def update_asset(aid: int, data: dict):
    sets = ", ".join([f"{k}=?" for k in data.keys()])
    with get_conn() as conn:
        conn.execute(f"UPDATE assets SET {sets} WHERE id=?", list(data.values()) + [aid])
        conn.commit()


def delete_asset(aid: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM assets WHERE id=?", (aid,))
        conn.commit()


def get_next_asset_tag():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()
        return f"KLKA-IT-{(row['c'] or 0) + 1:04d}"


def add_history(asset_id, action, detail, changed_by):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO asset_history (asset_id,action,detail,changed_by,changed_at) VALUES (?,?,?,?,?)",
            (asset_id, action, detail, changed_by, datetime.datetime.now().isoformat())
        )
        conn.commit()


def get_history(asset_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM asset_history WHERE asset_id=? ORDER BY changed_at DESC", (asset_id,)
        ).fetchall()]


def get_user_by_email(email):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def get_all_users():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY name").fetchall()]


def create_user(data: dict):
    cols = ", ".join(data.keys())
    ph   = ", ".join(["?"] * len(data))
    with get_conn() as conn:
        conn.execute(f"INSERT INTO users ({cols}) VALUES ({ph})", list(data.values()))
        conn.commit()


def count_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]


def get_warranty_expiring(days=30):
    import datetime as dt
    today = dt.date.today()
    limit = (today + dt.timedelta(days=days)).isoformat()
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM assets WHERE warranty_expiry != '' AND warranty_expiry IS NOT NULL AND warranty_expiry <= ? AND status='Active' ORDER BY warranty_expiry",
            (limit,)
        ).fetchall()]
