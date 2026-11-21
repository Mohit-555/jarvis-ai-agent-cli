import os
import tempfile
import unittest
from pathlib import Path

from tools.data.db_tool import DatabaseTool
from tools.office.document_tool import DocumentTool
from tools.code.project_scanner import ProjectScannerTool
from tools.os.file_manager import FileManagerTool
from tools.code.github_tool import GitHubTool


class Test180CapabilitiesMatrix(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_tool = DatabaseTool(workspace=str(self.root))
        self.doc_tool = DocumentTool(workspace=str(self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    # ── Database Capabilities (Tasks 106–120) ─────────────────────────
    def test_database_crud_and_export(self):
        db_file = str(self.root / "test.db")

        # 1. Create table
        create_res = self.db_tool.query(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);",
            db_type="sqlite",
            db_name=db_file,
            confirm=True,
        )
        self.assertTrue(create_res["success"], f"Create table failed: {create_res}")

        # 2. Insert records
        ins_res = self.db_tool.query(
            "INSERT INTO users (name, email) VALUES ('Mohit', 'mohit@example.com'), ('Alice', 'alice@example.com');",
            db_type="sqlite",
            db_name=db_file,
            confirm=True,
        )
        self.assertTrue(ins_res["success"])
        self.assertEqual(ins_res["affected_rows"], 2)

        # 3. List tables
        tbl_res = self.db_tool.list_tables(db_type="sqlite", db_name=db_file)
        self.assertTrue(tbl_res["success"])
        self.assertIn("users", tbl_res["tables"])

        # 4. Query records
        sel_res = self.db_tool.query("SELECT * FROM users ORDER BY id ASC;", db_type="sqlite", db_name=db_file)
        self.assertTrue(sel_res["success"])
        self.assertEqual(sel_res["row_count"], 2)
        self.assertEqual(sel_res["rows"][0]["name"], "Mohit")

        # 5. Export to CSV
        csv_out = str(self.root / "users.csv")
        exp_res = self.db_tool.export_csv("SELECT id, name, email FROM users;", csv_out, db_type="sqlite", db_name=db_file)
        self.assertTrue(exp_res["success"])
        self.assertTrue(os.path.exists(csv_out))
        content = Path(csv_out).read_text()
        self.assertIn("Mohit", content)
        self.assertIn("alice@example.com", content)

    # ── Office Document Capabilities (Tasks 171–180) ──────────────────
    def test_docx_generation_and_reading(self):
        docx_path = str(self.root / "test_report.docx")
        gen_res = self.doc_tool.generate(
            doc_type="docx",
            output_path=docx_path,
            title="Project Report",
            content="This is the main body text.\n\n## Section 1\nDetails here.",
            table_data=[["Metric", "Value"], ["Tests", "180"], ["Status", "Passed"]],
        )
        self.assertTrue(gen_res["success"], f"Docx generation failed: {gen_res}")
        self.assertTrue(os.path.exists(docx_path))

        read_res = self.doc_tool.read(docx_path)
        self.assertTrue(read_res["success"])
        self.assertIn("Project Report", read_res["content"])
        self.assertIn("Details here.", read_res["content"])

    def test_xlsx_generation_and_reading(self):
        xlsx_path = str(self.root / "metrics.xlsx")
        gen_res = self.doc_tool.generate(
            doc_type="xlsx",
            output_path=xlsx_path,
            title="Metrics",
            table_data=[["Task", "Completed"], ["Auth", "Yes"], ["Database", "Yes"]],
        )
        self.assertTrue(gen_res["success"])
        self.assertTrue(os.path.exists(xlsx_path))

        read_res = self.doc_tool.read(xlsx_path)
        self.assertTrue(read_res["success"])
        self.assertIn("Metrics", read_res["sheets"])

    def test_pdf_generation(self):
        pdf_path = str(self.root / "summary.pdf")
        gen_res = self.doc_tool.generate(
            doc_type="pdf",
            output_path=pdf_path,
            title="Weekly Summary",
            content="All systems operational.",
            table_data=[["Item", "Result"], ["API", "200 OK"]],
        )
        self.assertTrue(gen_res["success"], f"PDF generation failed: {gen_res}")
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500)

    def test_pptx_generation(self):
        pptx_path = str(self.root / "deck.pptx")
        gen_res = self.doc_tool.generate(
            doc_type="pptx",
            output_path=pptx_path,
            title="AI Architecture",
            slides=[
                {"title": "Overview", "content": "Jarvis 2.1.1 capabilities"},
                {"title": "Tools", "content": "Database, Office, Git, WhatsApp"},
            ],
        )
        self.assertTrue(gen_res["success"], f"PPTX generation failed: {gen_res}")
        self.assertTrue(os.path.exists(pptx_path))
        self.assertEqual(gen_res["slides_count"], 3)  # Title slide + 2 content slides

    def test_csv_to_excel_conversion(self):
        csv_file = self.root / "data.csv"
        csv_file.write_text("colA,colB\n10,20\n30,40")

        xlsx_out = str(self.root / "converted.xlsx")
        conv_res = self.doc_tool.convert(str(csv_file), xlsx_out)
        self.assertTrue(conv_res["success"])
        self.assertTrue(os.path.exists(xlsx_out))


if __name__ == "__main__":
    unittest.main()
