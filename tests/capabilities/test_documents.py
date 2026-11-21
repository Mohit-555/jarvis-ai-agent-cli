import os
import tempfile
import unittest
from pathlib import Path
from tools.office.document_tool import DocumentTool


class TestDocumentsCapabilities(unittest.TestCase):
    """
    Verification of Tasks 171–180: Document & Office Automation.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.doc = DocumentTool(workspace=str(self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_172_word_doc_generation_and_reading(self):
        """Tasks 172 & 175: Generate and read/summarize Word .docx."""
        docx_path = str(self.root / "report.docx")
        gen_res = self.doc.generate(
            doc_type="docx",
            output_path=docx_path,
            title="Quarterly Review",
            content="Summary of achievements.\n\n## Section 1\nDetails here.",
        )
        self.assertTrue(gen_res["success"])
        self.assertTrue(os.path.exists(docx_path))

        read_res = self.doc.read(docx_path)
        self.assertTrue(read_res["success"])
        self.assertIn("Quarterly Review", read_res["content"])

    def test_task_173_pdf_report_generation(self):
        """Task 173: Generate a PDF report."""
        pdf_path = str(self.root / "analytics.pdf")
        gen_res = self.doc.generate(
            doc_type="pdf",
            output_path=pdf_path,
            title="System Analytics",
            content="All services operational.",
            table_data=[["Service", "Status"], ["Gateway", "Active"]],
        )
        self.assertTrue(gen_res["success"])
        self.assertTrue(os.path.exists(pdf_path))

    def test_task_176_177_excel_generation_and_csv_conversion(self):
        """Tasks 176-178: Convert CSV to Excel, generate Excel report, read Excel."""
        csv_path = self.root / "records.csv"
        csv_path.write_text("ID,Name,Role\n1,Mohit,Lead\n2,Jarvis,AI")

        xlsx_path = str(self.root / "records.xlsx")
        conv_res = self.doc.convert(str(csv_path), xlsx_path)
        self.assertTrue(conv_res["success"])
        self.assertTrue(os.path.exists(xlsx_path))

        read_res = self.doc.read(xlsx_path)
        self.assertTrue(read_res["success"])
        self.assertIn("records", read_res["sheets"])

    def test_task_179_powerpoint_presentation(self):
        """Task 179: Create PowerPoint presentation."""
        pptx_path = str(self.root / "slides.pptx")
        gen_res = self.doc.generate(
            doc_type="pptx",
            output_path=pptx_path,
            title="Jarvis Architecture",
            slides=[
                {"title": "Overview", "content": "Autonomous Agent System"},
                {"title": "Tools", "content": "Database, Office, WhatsApp"},
            ],
        )
        self.assertTrue(gen_res["success"])
        self.assertTrue(os.path.exists(pptx_path))

    def test_task_workspace_path_containment_guard(self):
        """P0 Security: Prevent access to documents outside workspace."""
        outside_path = "/tmp/malicious_document.docx"
        res = self.doc.read(outside_path)
        self.assertFalse(res["success"])
        self.assertIn("Access Denied", res["error"])


if __name__ == "__main__":
    unittest.main()
