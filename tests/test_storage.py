import sqlite3
import tempfile
import unittest
from pathlib import Path

from baymax.storage import SCHEMA_VERSION, Store


class StoreTests(unittest.TestCase):
    def test_schema_version_health_and_rating_ids(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        self.assertEqual(store.health(), {"ok": True, "schema": SCHEMA_VERSION})
        rid = store.add_rating("u1", "physical", "pain", 7)
        self.assertGreater(rid, 0)
        self.assertEqual(store.ratings("u1")[0]["id"], rid)
        self.assertTrue(store.update_rating("u1", rid, 5))
        self.assertEqual(store.ratings("u1")[0]["rating"], 5)
        self.assertTrue(store.delete_rating("u1", rid))
        self.assertEqual(store.ratings("u1"), [])

    def test_settings_preserve_consent_version_as_string(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        saved = store.save_settings("u1", {"consented_version": "1", "auto_memory": False})
        self.assertEqual(saved["consented_version"], "1")
        self.assertIs(saved["auto_memory"], False)
        self.assertEqual(store.get_settings("u1")["consented_version"], "1")

    def test_transaction_rolls_back_all_writes_on_failure(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        with self.assertRaises(ValueError):
            store.persist_turn(
                "u1", pairs=[("user", "pain"), ("assistant", "reply")],
                emotion={"calmness": 0.5}, rating_event={"action": "record", "type": "physical",
                "subtype": "pain", "rating": 11}, bump=True,
            )
        self.assertEqual(store.history_with_time("u1"), [])
        self.assertEqual(store.get_emotion("u1"), {})
        self.assertEqual(store.usage_today("u1"), 0)

    def test_persist_turn_inserts_rating_and_messages_atomically(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        rid = store.persist_turn(
            "u1", pairs=[("user", "8/10"), ("assistant", "Thanks")],
            emotion={"calmness": 0.8}, rating_event={"action": "record", "type": "physical",
            "subtype": "pain", "rating": 8}, bump=True,
        )
        self.assertTrue(rid)
        self.assertEqual(store.ratings("u1")[0]["rating"], 8)
        self.assertEqual(len(store.history("u1")), 2)
        self.assertEqual(store.usage_today("u1"), 1)

    def test_legacy_database_is_backed_up_before_schema_upgrade(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "baymax.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE legacy (value TEXT)")
            conn.execute("INSERT INTO legacy VALUES ('preserve')")
            conn.execute("PRAGMA user_version = 0")
            conn.commit()
            conn.close()

            store = Store(str(db), backup_keep=2)
            self.assertEqual(store.health()["schema"], SCHEMA_VERSION)
            self.assertTrue(store.backup_path)
            self.assertTrue(Path(store.backup_path).exists())
            backup = sqlite3.connect(store.backup_path)
            try:
                self.assertEqual(backup.execute("SELECT value FROM legacy").fetchone()[0], "preserve")
            finally:
                backup.close()
            self.assertEqual(store.db.execute("SELECT value FROM legacy").fetchone()[0], "preserve")
            store.close()

    def test_delete_all_is_user_scoped(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        store.add_memory("u1", "likes pizza")
        store.add_memory("u2", "likes noodles")
        store.delete_all("u1")
        self.assertEqual(store.memories("u1"), [])
        self.assertEqual([x["fact"] for x in store.memories("u2")], ["likes noodles"])

    def test_export_includes_all_ratings_and_usage(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        store.db.executemany(
            "INSERT INTO ratings(user_id, ts, type, subtype, rating) VALUES (?,?,?,?,?)",
            [("u1", "2026-01-01T00:00:00", "physical", "pain", i % 11) for i in range(1005)],
        )
        store.db.execute("INSERT INTO usage(user_id, day, count) VALUES (?,?,?)", ("u1", "2026-01-01", 12))
        store.db.commit()
        exported = store.export("u1")
        self.assertEqual(len(exported["ratings"]), 1005)
        self.assertEqual(exported["usage"], [{"day": "2026-01-01", "count": 12}])

    def test_purge_backups_removes_matching_migration_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "baymax.db"
            store = Store(str(db))
            store.close()
            backup = Path(td) / "baymax.db.pre-migration-test.bak"
            backup.write_text("private chat data", encoding="utf-8")
            unrelated = Path(td) / "other.bak"
            unrelated.write_text("keep", encoding="utf-8")
            cleaner = Store(str(db))
            try:
                self.assertEqual(cleaner.purge_backups(), 1)
                self.assertFalse(backup.exists())
                self.assertTrue(unrelated.exists())
            finally:
                cleaner.close()

    def test_history_and_memories_are_retained_without_automatic_pruning(self):
        store = Store(":memory:")
        self.addCleanup(store.close)
        for i in range(301):
            store.add_messages("u1", [("user", f"message {i}")])
        for i in range(101):
            store.add_memory("u1", f"fact {i}")
        all_messages = store._all("SELECT id, content FROM messages WHERE user_id=? ORDER BY id", ("u1",))
        self.assertEqual(len(all_messages), 301)
        self.assertEqual(all_messages[0]["content"], "message 0")
        self.assertEqual(len(store.memories("u1")), 101)
        self.assertEqual(len(store.history("u1", 24)), 24)

    def test_read_only_owner_export_lists_both_users_without_changing_database(self):
        import hashlib
        from tools.export_all import export_all

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "baymax.db"
            store = Store(str(db))
            store.add_messages("u1", [("user", "hello"), ("assistant", "hi")])
            store.add_memory("u1", "likes dosa")
            store.add_rating("u1", "physical", "pain", 4)
            store.add_feedback("u1", "be more concise")
            store.save_emotion("u1", {"concern": 0.2})
            store.bump_usage("u1")
            store.add_messages("u2", [("user", "hello from friend")])
            store.add_memory("u2", "likes noodles")
            store.add_rating("u2", "emotional", "feeling", 7)
            store.save_emotion("u2", {"calmness": 0.8})
            store.bump_usage("u2")
            store.close()

            before = hashlib.sha256(db.read_bytes()).hexdigest()
            exported = export_all(str(db))
            after = hashlib.sha256(db.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(set(exported["users"]), {"u1", "u2"})
            self.assertEqual(exported["users"]["u1"]["messages"][0]["content"], "hello")
            self.assertEqual(exported["users"]["u2"]["memories"][0]["fact"], "likes noodles")
            self.assertEqual(exported["users"]["u1"]["ratings"][0]["rating"], 4)
            self.assertEqual(exported["users"]["u1"]["feedback"][0]["text"], "be more concise")
            self.assertEqual(exported["users"]["u2"]["emotion"]["calmness"], 0.8)
            self.assertTrue(exported["users"]["u2"]["usage"])


if __name__ == "__main__":
    unittest.main()
