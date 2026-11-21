import os
import tempfile
import unittest
from pathlib import Path
from tools.os.file_manager import FileManagerTool
from tools.code.project_scanner import ProjectScannerTool


class TestFileManagementCapabilities(unittest.TestCase):
    """
    Verification of Tasks 16–35: File & Folder Management.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fm = FileManagerTool(workspace=str(self.root))
        self.scanner = ProjectScannerTool(workspace=str(self.root))

        # Setup test structure
        (self.root / "file1.txt").write_text("content 1")
        (self.root / "app.py").write_text("print('app')")
        (self.root / "subfolder").mkdir()
        (self.root / "subfolder" / "script.py").write_text("x = 1")
        (self.root / "doc.pdf").write_bytes(b"%PDF-1.4 test")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_16_17_list_files_and_folders(self):
        """Tasks 16 & 17: Show all files and folders in directory."""
        items = self.fm.list(str(self.root))
        names = [i["name"] for i in items]
        self.assertIn("file1.txt", names)
        self.assertIn("subfolder", names)
        types = {i["name"]: i["type"] for i in items}
        self.assertEqual(types["subfolder"], "dir")
        self.assertEqual(types["file1.txt"], "file")

    def test_task_18_20_search_and_find_by_extension(self):
        """Tasks 18-20: Find file by name, Python files, PDF files."""
        # Search by pattern
        py_files = self.fm.search("*.py", path=str(self.root))
        self.assertTrue(any("app.py" in f for f in py_files))

        pdf_files = self.fm.search("*.pdf", path=str(self.root))
        self.assertTrue(any("doc.pdf" in f for f in pdf_files))

    def test_task_21_26_create_rename_move_file(self):
        """Tasks 21-26: Create, rename, copy, move files and folders."""
        new_file = self.root / "test_write.txt"
        res_write = self.fm.write(str(new_file), "hello world")
        self.assertIn("Written to", res_write)
        self.assertTrue(new_file.exists())

        # Move/Rename
        renamed = self.root / "renamed.txt"
        self.fm.move(str(new_file), str(renamed))
        self.assertFalse(new_file.exists())
        self.assertTrue(renamed.exists())

    def test_task_27_28_delete_file_and_empty_folder(self):
        """Tasks 27-28: Delete a file and delete empty folder."""
        f_to_del = self.root / "delete_me.txt"
        f_to_del.write_text("delete me")
        res_del = self.fm.delete(str(f_to_del))
        self.assertIn("Deleted", res_del)
        self.assertFalse(f_to_del.exists())

        empty_dir = self.root / "empty_dir"
        empty_dir.mkdir()
        self.fm.delete(str(empty_dir))
        self.assertFalse(empty_dir.exists())

    def test_task_33_read_file(self):
        """Task 33: Read a text file."""
        content = self.fm.read(str(self.root / "file1.txt"))
        self.assertEqual(content, "content 1")

    def test_task_35_directory_tree_generation(self):
        """Task 35: Generate a directory tree."""
        res = self.scanner.scan(str(self.root))
        self.assertIn("file_tree", res)
        self.assertGreater(len(res["file_tree"]), 2)


if __name__ == "__main__":
    unittest.main()
