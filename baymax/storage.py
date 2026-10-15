"""SQLite persistence. One file, per-user rows, no server needed."""
import json
import shutil
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
    fact TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
    role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS emotion(user_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(user_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ratings(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
    ts TEXT NOT NULL, type TEXT, subtype TEXT, rating INTEGER);
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
    ts TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage(user_id TEXT NOT NULL, day TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(user_id, day));
CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_msg_user ON messages(user_id, id);
CREATE INDEX IF NOT EXISTS idx_rat_user ON ratings(user_id, id);
"""

DEFAULT_SETTINGS = {"auto_memory": True, "speak": True, "consented_version": ""}
MAX_MEMORIES = 100
MAX_MESSAGES = 300
SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str = ":memory:", backup_keep: int = 7):
        self.path = path
        self.backup_keep = max(1, int(backup_keep))
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        existed = path != ":memory:" and Path(path).is_file() and Path(path).stat().st_size > 0
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.backup_path = None
        try:
            version = int(self.db.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema version {version} is newer than this application supports ({SCHEMA_VERSION})."
                )
            if version < SCHEMA_VERSION and existed:
                self.backup_path = self._backup_before_migration(path)
            self._migrate(version)
        except Exception:
            try:
                self.db.close()
            finally:
                if self.backup_path and Path(self.backup_path).exists():
                    shutil.copy2(self.backup_path, path)
            raise

    def _backup_before_migration(self, path: str) -> str:
        source = Path(path)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        backup = source.with_name(f"{source.name}.pre-migration-{stamp}.bak")
        target = sqlite3.connect(str(backup))
        try:
            self.db.backup(target)
        finally:
            target.close()
        if self.backup_keep >= 0:
            backups = sorted(source.parent.glob(f"{source.name}.pre-migration-*.bak"),
                             key=lambda p: p.stat().st_mtime, reverse=True)
            for old in backups[max(1, self.backup_keep):]:
                try:
                    old.unlink()
                except OSError:
                    pass
        return str(backup)

    def _migrate(self, version: int):
        """Apply ordered, transactional schema migrations. Version 1 is the baseline schema."""
        with self._lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                if version < 1:
                    for statement in SCHEMA.split(";"):
                        if statement.strip():
                            self.db.execute(statement)
                    self.db.execute("PRAGMA user_version = 1")
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def close(self):
        with self._lock:
            self.db.close()

    def _run(self, sql, args=()):
        with self._lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def _all(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def persist_turn(self, uid, pairs=None, emotion=None, rating_event=None, memory=None, bump=True):
        """Persist one turn's writes atomically; return inserted/updated rating and memory IDs."""
        result = {"rating_id": None, "memory_id": None}
        with self._lock:
            with self.db:
                if pairs is not None:
                    for role, content in pairs:
                        self.db.execute(
                            "INSERT INTO messages(user_id, role, content, ts) VALUES (?,?,?,?)",
                            (uid, role, content, _now()),
                        )
                    self.db.execute(
                        "DELETE FROM messages WHERE user_id=? AND id NOT IN "
                        "(SELECT id FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?)",
                        (uid, uid, MAX_MESSAGES),
                    )
                if emotion is not None:
                    self.db.execute(
                        "INSERT INTO emotion(user_id, data) VALUES (?,?) "
                        "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data",
                        (uid, json.dumps(emotion)),
                    )
                if rating_event:
                    action = rating_event.get("action", "record")
                    rating = int(rating_event["rating"])
                    if not 0 <= rating <= 10:
                        raise ValueError("rating must be between 0 and 10")
                    if action == "correct":
                        rid = int(rating_event["id"])
                        cur = self.db.execute(
                            "UPDATE ratings SET rating=? WHERE id=? AND user_id=?", (rating, rid, uid)
                        )
                        if cur.rowcount:
                            result["rating_id"] = rid
                    elif action == "record":
                        cur = self.db.execute(
                            "INSERT INTO ratings(user_id, ts, type, subtype, rating) VALUES (?,?,?,?,?)",
                            (uid, _now(), rating_event["type"], rating_event["subtype"], rating),
                        )
                        result["rating_id"] = int(cur.lastrowid)
                if memory:
                    cur = self.db.execute(
                        "INSERT INTO memories(user_id, fact, created) VALUES (?,?,?)", (uid, memory.strip(), _now())
                    )
                    result["memory_id"] = int(cur.lastrowid)
                    self.db.execute(
                        "DELETE FROM memories WHERE user_id=? AND id NOT IN "
                        "(SELECT id FROM memories WHERE user_id=? ORDER BY id DESC LIMIT ?)",
                        (uid, uid, MAX_MEMORIES),
                    )
                if bump:
                    self.db.execute(
                        "INSERT INTO usage(user_id, day, count) VALUES (?,?,1) "
                        "ON CONFLICT(user_id, day) DO UPDATE SET count=count+1",
                        (uid, date.today().isoformat()),
                    )
        return result

    def health(self) -> dict:
        try:
            with self._lock:
                self.db.execute("SELECT 1").fetchone()
                version = int(self.db.execute("PRAGMA user_version").fetchone()[0])
            return {"ok": True, "schema": version}
        except sqlite3.Error:
            return {"ok": False, "schema": None}

    # ---- memories
    def memories(self, uid):
        return self._all("SELECT id, fact, created FROM memories WHERE user_id=? ORDER BY id", (uid,))

    def add_memory(self, uid, fact: str):
        with self._lock:
            cur = self.db.execute("INSERT INTO memories(user_id, fact, created) VALUES (?,?,?)",
                                  (uid, fact.strip(), _now()))
            memory_id = int(cur.lastrowid)
            self.db.execute("DELETE FROM memories WHERE user_id=? AND id NOT IN "
                            "(SELECT id FROM memories WHERE user_id=? ORDER BY id DESC LIMIT ?)",
                            (uid, uid, MAX_MEMORIES))
            self.db.commit()
            return memory_id

    def delete_memory(self, uid, mem_id: int) -> bool:
        return self._run("DELETE FROM memories WHERE user_id=? AND id=?", (uid, mem_id)).rowcount > 0

    def clear_memories(self, uid):
        self._run("DELETE FROM memories WHERE user_id=?", (uid,))

    # ---- conversation history
    def add_messages(self, uid, pairs):
        for role, content in pairs:
            self._run("INSERT INTO messages(user_id, role, content, ts) VALUES (?,?,?,?)",
                      (uid, role, content, _now()))
        self._run("DELETE FROM messages WHERE user_id=? AND id NOT IN "
                  "(SELECT id FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?)", (uid, uid, MAX_MESSAGES))

    def history(self, uid, limit=24):
        rows = self._all("SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit))
        return rows[::-1]

    def history_with_time(self, uid, limit=40):
        rows = self._all("SELECT role, content, ts FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                         (uid, limit))
        return rows[::-1]

    def clear_history(self, uid):
        self._run("DELETE FROM messages WHERE user_id=?", (uid,))

    # ---- emotion + settings
    def get_emotion(self, uid) -> dict:
        r = self._all("SELECT data FROM emotion WHERE user_id=?", (uid,))
        return json.loads(r[0]["data"]) if r else {}

    def save_emotion(self, uid, data: dict):
        self._run("INSERT INTO emotion(user_id, data) VALUES (?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data", (uid, json.dumps(data)))

    def get_settings(self, uid) -> dict:
        r = self._all("SELECT data FROM settings WHERE user_id=?", (uid,))
        saved = json.loads(r[0]["data"]) if r else {}
        return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}

    def save_settings(self, uid, data: dict):
        clean = {}
        for key, value in data.items():
            if key not in DEFAULT_SETTINGS:
                continue
            if key == "consented_version":
                # A version marker, not a health/profile field; cap it to avoid arbitrary payloads.
                if isinstance(value, str) and len(value) <= 40:
                    clean[key] = value
            else:
                clean[key] = bool(value)
        merged = {**self.get_settings(uid), **clean}
        self._run("INSERT INTO settings(user_id, data) VALUES (?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data", (uid, json.dumps(merged)))
        return merged

    # ---- ratings, feedback, usage
    def add_rating(self, uid, type_, subtype, rating):
        value = int(rating)
        if not 0 <= value <= 10:
            raise ValueError("rating must be between 0 and 10")
        with self._lock:
            cur = self.db.execute("INSERT INTO ratings(user_id, ts, type, subtype, rating) VALUES (?,?,?,?,?)",
                                  (uid, _now(), type_, subtype, value))
            self.db.commit()
            return int(cur.lastrowid)

    def ratings(self, uid, limit=50):
        if limit is None:
            rows = self._all("SELECT id, ts, type, subtype, rating FROM ratings WHERE user_id=? ORDER BY id DESC",
                             (uid,))
        else:
            rows = self._all("SELECT id, ts, type, subtype, rating FROM ratings WHERE user_id=? ORDER BY id DESC LIMIT ?",
                             (uid, limit))
        return rows[::-1]

    def update_rating(self, uid, rating_id: int, rating: int) -> bool:
        value = int(rating)
        if not 0 <= value <= 10:
            raise ValueError("rating must be between 0 and 10")
        return self._run("UPDATE ratings SET rating=? WHERE id=? AND user_id=?", (value, int(rating_id), uid)).rowcount > 0

    def delete_rating(self, uid, rating_id: int) -> bool:
        return self._run("DELETE FROM ratings WHERE id=? AND user_id=?", (int(rating_id), uid)).rowcount > 0

    def add_feedback(self, uid, text: str):
        self._run("INSERT INTO feedback(user_id, ts, text) VALUES (?,?,?)", (uid, _now(), text))

    def usage_today(self, uid) -> int:
        r = self._all("SELECT count FROM usage WHERE user_id=? AND day=?", (uid, date.today().isoformat()))
        return r[0]["count"] if r else 0

    def bump_usage(self, uid):
        self._run("INSERT INTO usage(user_id, day, count) VALUES (?,?,1) "
                  "ON CONFLICT(user_id, day) DO UPDATE SET count=count+1", (uid, date.today().isoformat()))

    # ---- privacy: export and delete everything for one user
    def export(self, uid) -> dict:
        return {"memories": self.memories(uid), "messages": self.history_with_time(uid, MAX_MESSAGES),
                "emotion": self.get_emotion(uid), "settings": self.get_settings(uid),
                "ratings": self.ratings(uid, None),
                "feedback": self._all("SELECT ts, text FROM feedback WHERE user_id=? ORDER BY id", (uid,)),
                "usage": self._all("SELECT day, count FROM usage WHERE user_id=? ORDER BY day", (uid,))}

    def purge_backups(self) -> int:
        """Remove pre-migration database snapshots that may retain deleted conversation data."""
        if self.path == ":memory:":
            return 0
        source = Path(self.path)
        removed = 0
        for backup in source.parent.glob(f"{source.name}.pre-migration-*.bak"):
            # Surface failures so the service does not claim deletion succeeded while a
            # rollback snapshot containing the user's data remains on disk.
            backup.unlink()
            removed += 1
        return removed

    def delete_all(self, uid):
        with self._lock:
            with self.db:
                for table in ("memories", "messages", "emotion", "settings", "ratings", "feedback", "usage"):
                    self.db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
