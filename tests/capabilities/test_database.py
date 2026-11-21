import os
import tempfile
import unittest
from pathlib import Path
from tools.data.db_tool import DatabaseTool


class TestDatabaseCapabilities(unittest.TestCase):
    """
    Verification of Tasks 106–120: Database Management & SQL Security.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = str(self.root / "test.db")
        self.db = DatabaseTool(workspace=str(self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_106_114_sqlite_crud_and_confirmation_guard(self):
        """Tasks 106-114: Database operations with destructive mutation confirmation guard."""
        # 1. CREATE TABLE without confirm must be blocked
        res_blocked = self.db.query("CREATE TABLE products (id INT, name TEXT);", db_type="sqlite", db_name=self.db_path)
        self.assertFalse(res_blocked["success"])
        self.assertTrue(res_blocked.get("requires_confirmation"))

        # 2. CREATE TABLE with confirm=True must succeed
        res_create = self.db.query(
            "CREATE TABLE products (id INT, name TEXT);",
            db_type="sqlite",
            db_name=self.db_path,
            confirm=True,
        )
        self.assertTrue(res_create["success"])

        # 3. INSERT with confirm=True
        res_ins = self.db.query(
            "INSERT INTO products (id, name) VALUES (1, 'Laptop');",
            db_type="sqlite",
            db_name=self.db_path,
            confirm=True,
        )
        self.assertTrue(res_ins["success"])

        # 4. SELECT (read-only) runs in auto-mode without confirm=True
        res_sel = self.db.query("SELECT * FROM products;", db_type="sqlite", db_name=self.db_path)
        self.assertTrue(res_sel["success"])
        self.assertEqual(res_sel["row_count"], 1)
        self.assertEqual(res_sel["rows"][0]["name"], "Laptop")

    def test_task_108_list_tables(self):
        """Task 108: List available database tables."""
        self.db.query("CREATE TABLE items (id INT);", db_type="sqlite", db_name=self.db_path, confirm=True)
        res = self.db.list_tables(db_type="sqlite", db_name=self.db_path)
        self.assertTrue(res["success"])
        self.assertIn("items", res["tables"])

    def test_task_117_export_records_to_csv(self):
        """Task 117: Export database records to CSV."""
        self.db.query("CREATE TABLE employees (id INT, name TEXT);", db_type="sqlite", db_name=self.db_path, confirm=True)
        self.db.query("INSERT INTO employees VALUES (101, 'Mohit');", db_type="sqlite", db_name=self.db_path, confirm=True)

        csv_file = str(self.root / "employees.csv")
        res_exp = self.db.export_csv("SELECT id, name FROM employees;", csv_file, db_type="sqlite", db_name=self.db_path)
        self.assertTrue(res_exp["success"])
        self.assertTrue(os.path.exists(csv_file))
        self.assertIn("Mohit", Path(csv_file).read_text())

    def test_task_workspace_path_containment_guard(self):
        """P0 Security: Prevent access to SQLite databases outside the workspace."""
        outside_path = "/tmp/malicious_outside_workspace.db"
        res = self.db.query("SELECT 1;", db_type="sqlite", db_name=outside_path)
        self.assertFalse(res["success"])
        self.assertIn("Access Denied", res["error"])


if __name__ == "__main__":
    unittest.main()
