import importlib.util
import os
import sqlite3
import tempfile
import unittest

APP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mini_kakeibo.py"
)


def load_app(db_path):
    spec = importlib.util.spec_from_file_location("mini_kakeibo", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_PATH = db_path
    module.init_db()
    return module


class KakeiboTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db_path)
        self.mod = load_app(self.db_path)
        self.client = self.mod.app.test_client()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def count(self):
        c = sqlite3.connect(self.db_path)
        n = c.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        c.close()
        return n

    def add_one(self):
        return self.client.post(
            "/add",
            data={
                "entry_date": "2026-10-27",
                "kind": "expense",
                "category": "食費",
                "amount": "500",
                "memo": "lunch",
            },
        )

    def test_index_ok(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_add_entry(self):
        self.add_one()
        self.assertEqual(self.count(), 1)

    def test_add_bad_amount_ignored(self):
        self.client.post(
            "/add",
            data={
                "entry_date": "2026-10-27",
                "kind": "expense",
                "category": "食費",
                "amount": "abc",
                "memo": "",
            },
        )
        self.assertEqual(self.count(), 0)

    def test_delete_entry(self):
        self.add_one()
        c = sqlite3.connect(self.db_path)
        mid = c.execute("SELECT id FROM entries").fetchone()[0]
        c.close()
        self.client.post(f"/delete/{mid}", data={"month": "2026-10"})
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
