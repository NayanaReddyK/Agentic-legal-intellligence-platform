import sqlite3
from datetime import datetime

DB = "legal_assistant.db"


def _conn():
    return sqlite3.connect(DB)


def init_db():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS review_history (
            contract TEXT, finding_key TEXT, decision TEXT, edited_fix TEXT, lawyer_note TEXT, decided_at TEXT,
            PRIMARY KEY (contract, finding_key))""")
        c.execute("""CREATE TABLE IF NOT EXISTS review_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, contract TEXT, finding_key TEXT,
            decision TEXT, edited_fix TEXT, lawyer_note TEXT, at TEXT)""")


def save_decision(contract: str, key: str, decision: str, fix: str, note: str):
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO review_history VALUES (?,?,?,?,?,?)", (contract, key, decision, fix, note, now))
        c.execute("INSERT INTO review_log (contract, finding_key, decision, edited_fix, lawyer_note, at) VALUES (?,?,?,?,?,?)",
                  (contract, key, decision, fix, note, now))   # append-only audit trail


def load_decisions(contract: str) -> dict:
    with _conn() as c:
        rows = c.execute("SELECT finding_key, decision, edited_fix, lawyer_note FROM review_history WHERE contract=?",
                         (contract,)).fetchall()
    return {k: {"decision": d, "fix": f, "note": n} for k, d, f, n in rows}