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


if __name__ == "__main__":
    unittest.main()
