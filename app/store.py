import sqlite3
from app.config import DATABASE_PATH

def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)

def init_db():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, input_sha256 TEXT NOT NULL, accepted INTEGER NOT NULL, quarantined INTEGER NOT NULL)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS determinations ("
            "determination_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, connection_key TEXT NOT NULL, "
            "decision TEXT NOT NULL, status TEXT NOT NULL, wait_minutes INTEGER, required_minutes INTEGER, "
            "superseded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS confirmations ("
            "confirmation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, "
            "leg_key TEXT NOT NULL, payload_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), "
            "UNIQUE(run_id, kind, leg_key, payload_hash))"
        )

def record_run(manifest: dict) -> bool:
    init_db()
    with connect() as db:
        before = db.total_changes
        db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?)", (manifest["run_id"], manifest["input_sha256"], manifest["accepted"], manifest["quarantined"]))
        return db.total_changes > before

def run_count() -> int:
    init_db()
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]


# ---------- 衔接判定台账 ----------

def _rows(db, sql: str, params: tuple = ()) -> list[dict]:
    cursor = db.execute(sql, params)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def replace_determinations(run_id: str, connection_keys: list[str]) -> None:
    """航司晚到确认触发重算：旧判定先整体失效，再落新一轮判定。"""
    init_db()
    with connect() as db:
        db.execute("UPDATE determinations SET superseded = 1 WHERE run_id = ? AND superseded = 0", (run_id,))


def save_determination(record: dict) -> bool:
    init_db()
    with connect() as db:
        before = db.total_changes
        db.execute(
            "INSERT OR IGNORE INTO determinations "
            "(determination_id, run_id, connection_key, decision, status, wait_minutes, required_minutes, superseded) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (
                record["determination_id"], record["run_id"], record["connection_key"],
                record["decision"], record["status"], record.get("wait_minutes"),
                record.get("required_minutes"),
            ),
        )
        return db.total_changes > before


def list_determinations(run_id: str, include_superseded: bool = False) -> list[dict]:
    init_db()
    sql = "SELECT * FROM determinations WHERE run_id = ?"
    if not include_superseded:
        sql += " AND superseded = 0"
    sql += " ORDER BY connection_key, created_at"
    with connect() as db:
        return _rows(db, sql, (run_id,))


def record_confirmation(record: dict) -> bool:
    """同一条确认（同 run、同类型、同航段、同负载哈希）重跑不新增记录。"""
    init_db()
    with connect() as db:
        before = db.total_changes
        db.execute(
            "INSERT OR IGNORE INTO confirmations (confirmation_id, run_id, kind, leg_key, payload_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            (record["confirmation_id"], record["run_id"], record["kind"], record["leg_key"], record["payload_hash"]),
        )
        return db.total_changes > before


def list_confirmations(run_id: str) -> list[dict]:
    init_db()
    with connect() as db:
        return _rows(db, "SELECT * FROM confirmations WHERE run_id = ? ORDER BY created_at", (run_id,))
