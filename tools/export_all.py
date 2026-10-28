#!/usr/bin/env python3
"""Read-only owner export of all Tiny Baymax user data."""
import argparse
import json
import os
import sqlite3
from pathlib import Path

TABLES = {
    "messages": "SELECT id, role, content, ts FROM messages WHERE user_id=? ORDER BY id",
    "memories": "SELECT id, fact, created FROM memories WHERE user_id=? ORDER BY id",
    "ratings": "SELECT id, ts, type, subtype, rating FROM ratings WHERE user_id=? ORDER BY id",
    "feedback": "SELECT id, ts, text FROM feedback WHERE user_id=? ORDER BY id",
    "emotion": "SELECT data FROM emotion WHERE user_id=?",
    "usage": "SELECT day, count FROM usage WHERE user_id=? ORDER BY day",
}


def rows(conn, sql, user_id):
    return [dict(row) for row in conn.execute(sql, (user_id,)).fetchall()]


def export_all(db_path):
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"SQLite database not found: {path}")
    uri = path.as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        user_ids = set()
        for table in TABLES:
            user_ids.update(row[0] for row in conn.execute(f"SELECT DISTINCT user_id FROM {table}").fetchall())
        users = {}
        for user_id in sorted(user_ids):
            emotion_rows = rows(conn, TABLES["emotion"], user_id)
            emotion = json.loads(emotion_rows[0]["data"]) if emotion_rows else {}
            users[user_id] = {
                "messages": rows(conn, TABLES["messages"], user_id),
                "memories": rows(conn, TABLES["memories"], user_id),
                "ratings": rows(conn, TABLES["ratings"], user_id),
                "feedback": rows(conn, TABLES["feedback"], user_id),
                "emotion": emotion,
                "usage": rows(conn, TABLES["usage"], user_id),
            }
        return {"users": users}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Print all Tiny Baymax user data as JSON (read-only).")
    parser.add_argument("database", nargs="?", default=os.environ.get("BAYMAX_DB", "data/baymax.db"),
                        help="SQLite database path (default: BAYMAX_DB or data/baymax.db)")
    args = parser.parse_args()
    print(json.dumps(export_all(args.database), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
