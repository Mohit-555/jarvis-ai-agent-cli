"""
DocumentTool - Office document generation, conversion, and inspection tool for Jarvis.
Supports Word (.docx), Excel (.xlsx), PDF (.pdf), PowerPoint (.pptx), and CSV operations.
"""

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DocumentTool:
    """Unified document generator, reader, and converter."""

    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace).resolve() if workspace else None

    def _resolve_path(self, path: str) -> Path:
        p = Path(path).expanduser().resolve()
        if self.workspace and not str(p).startswith(str(self.workspace)):
            pass
        return p

    def read(self, file_path: str, max_chars: int = 15000) -> Dict[str, Any]:
        """Read and extract textual content from PDF, Word (.docx), Excel (.xlsx), or CSV."""
        try:
            p = self._resolve_path(file_path)
            if not p.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            ext = p.suffix.lower()

            # Word .docx
            if ext == ".docx":
                import docx
                doc = docx.Document(str(p))
                paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
                text = "\n\n".join(paragraphs)
                return {
                    "success": True,
                    "format": "docx",
                    "file_path": str(p),
                    "paragraphs_count": len(paragraphs),
                    "content": text[:max_chars],
                }

            # PDF .pdf
            elif ext == ".pdf":
                text = ""
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(p))
                    pages = [page.extract_text() or "" for page in reader.pages]
                    text = "\n\n--- Page Break ---\n\n".join(pages)
                except Exception:
                    try:
                        import pdfplumber
                        with pdfplumber.open(str(p)) as pdf:
                            pages = [page.extract_text() or "" for page in pdf.pages]
                            text = "\n\n--- Page Break ---\n\n".join(pages)
                    except Exception as e:
                        return {"success": False, "error": f"Failed to extract PDF text: {e}"}

                return {
                    "success": True,
                    "format": "pdf",
                    "file_path": str(p),
                    "content": text[:max_chars],
                }

            # Excel .xlsx / .xls
            elif ext in (".xlsx", ".xlsm", ".xltx"):
                import openpyxl
                wb = openpyxl.load_workbook(str(p), data_only=True)
                sheets_data = {}
                for sheetname in wb.sheetnames:
                    ws = wb[sheetname]
                    rows = []
                    for row in ws.iter_rows(values_only=True):
                        if any(v is not None for v in row):
                            rows.append([str(v) if v is not None else "" for v in row])
                    sheets_data[sheetname] = rows[:100]

                return {
                    "success": True,
                    "format": "xlsx",
                    "file_path": str(p),
                    "sheets": sheets_data,
                    "summary": f"Loaded workbook with {len(sheets_data)} sheet(s): {', '.join(sheets_data.keys())}",
                }

            # CSV / TSV
            elif ext in (".csv", ".tsv"):
                delimiter = "\t" if ext == ".tsv" else ","
                rows = []
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    for r in reader:
                        rows.append(r)
                return {
                    "success": True,
                    "format": "csv",
                    "file_path": str(p),
                    "rows_count": len(rows),
                    "headers": rows[0] if rows else [],
                    "preview_rows": rows[:20],
                }

            # Plain text / Markdown / JSON
            else:
                text = p.read_text(encoding="utf-8", errors="replace")
                return {
                    "success": True,
                    "format": "text",
                    "file_path": str(p),
                    "content": text[:max_chars],
                }
        except Exception as e:
            return {"success": False, "error": str(e), "file_path": file_path}

    def generate(
        self,
        doc_type: str,
        output_path: str,
        title: str = "Document",
        content: str = "",
        table_data: Optional[List[List[Any]]] = None,
        slides: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a Word (.docx), Excel (.xlsx), PDF (.pdf), or PowerPoint (.pptx) document.
        """
        try:
            p = self._resolve_path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            doc_type = (doc_type or p.suffix.lstrip(".")).lower()

            # 1. Word Document (.docx)
            if doc_type in ("docx", "word", "doc"):
                import docx
                from docx.shared import Inches, Pt, RGBColor
                doc = docx.Document()
                doc.add_heading(title, level=0)

                if content:
                    for paragraph in content.split("\n\n"):
                        p_clean = paragraph.strip()
                        if p_clean.startswith("## "):
                            doc.add_heading(p_clean[3:], level=1)
                        elif p_clean.startswith("### "):
                            doc.add_heading(p_clean[4:], level=2)
                        elif p_clean.startswith("- "):
                            for line in p_clean.split("\n"):
                                doc.add_paragraph(line.lstrip("- *").strip(), style="List Bullet")
                        else:
                            doc.add_paragraph(p_clean)

                if table_data and len(table_data) > 0:
                    headers = table_data[0]
                    rows = table_data[1:]
                    table = doc.add_table(rows=1, cols=len(headers))
                    table.style = "Table Grid"
                    hdr_cells = table.rows[0].cells
                    for i, h in enumerate(headers):
                        hdr_cells[i].text = str(h)
                    for row in rows:
                        row_cells = table.add_row().cells
                        for i, val in enumerate(row):
                            if i < len(row_cells):
                                row_cells[i].text = str(val)

                doc.save(str(p))
                return {
                    "success": True,
                    "doc_type": "docx",
                    "output_path": str(p),
                    "message": f"Successfully created Word document at {p}",
                }

            # 2. Excel Spreadsheet (.xlsx)
            elif doc_type in ("xlsx", "excel", "sheet"):
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = title[:30] if title else "Sheet1"

                # If table_data provided
                if table_data and len(table_data) > 0:
                    for row in table_data:
                        ws.append(row)
                    # Style headers
                    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
                    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                    for cell in ws[1]:
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                elif content:
                    ws.append([title])
                    ws["A1"].font = Font(size=14, bold=True)
                    for line in content.split("\n"):
                        parts = line.split(",") if "," in line else [line]
                        ws.append([p.strip() for p in parts])

                wb.save(str(p))
                return {
                    "success": True,
                    "doc_type": "xlsx",
                    "output_path": str(p),
                    "message": f"Successfully created Excel spreadsheet at {p}",
                }

            # 3. PDF Document (.pdf)
            elif doc_type in ("pdf", "report"):
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib import colors

                doc = SimpleDocTemplate(str(p), pagesize=letter)
                styles = getSampleStyleSheet()
                story = []

                # Title
                title_style = ParagraphStyle(
                    'DocTitle',
                    parent=styles['Heading1'],
                    fontSize=22,
                    leading=26,
                    textColor=colors.HexColor("#1A365D"),
                    spaceAfter=15,
                )
                story.append(Paragraph(title, title_style))
                story.append(Spacer(1, 10))

                # Content paragraphs
                if content:
                    body_style = ParagraphStyle(
                        'DocBody',
                        parent=styles['Normal'],
                        fontSize=10,
                        leading=14,
                        textColor=colors.HexColor("#2D3748"),
                        spaceAfter=8,
                    )
                    h2_style = ParagraphStyle(
                        'DocH2',
                        parent=styles['Heading2'],
                        fontSize=14,
                        leading=18,
                        textColor=colors.HexColor("#2B6CB0"),
                        spaceBefore=10,
                        spaceAfter=6,
                    )
                    for block in content.split("\n\n"):
                        block_clean = block.strip()
                        if block_clean.startswith("## ") or block_clean.startswith("### "):
                            story.append(Paragraph(block_clean.lstrip("# ").strip(), h2_style))
                        else:
                            clean_text = block_clean.replace("\n", "<br/>")
                            story.append(Paragraph(clean_text, body_style))

                # Optional table
                if table_data and len(table_data) > 0:
                    story.append(Spacer(1, 10))
                    t = Table(table_data)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#F7FAFC")]),
                    ]))
                    story.append(t)

                doc.build(story)
                return {
                    "success": True,
                    "doc_type": "pdf",
                    "output_path": str(p),
                    "message": f"Successfully created PDF report at {p}",
                }

            # 4. PowerPoint Presentation (.pptx)
            elif doc_type in ("pptx", "presentation", "powerpoint"):
                from pptx import Presentation
                from pptx.util import Inches, Pt
                prs = Presentation()

                # Title Slide
                title_slide_layout = prs.slide_layouts[0]
                slide = prs.slides.add_slide(title_slide_layout)
                slide.shapes.title.text = title
                if content:
                    slide.placeholders[1].text = content[:200]

                # Additional slides
                slide_list = slides or []
                if not slide_list and content and "\n\n" in content:
                    # Auto-split content blocks into slides
                    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
                    for b in blocks:
                        lines = b.split("\n")
                        s_title = lines[0].lstrip("# -*").strip()
                        s_body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
                        slide_list.append({"title": s_title, "content": s_body})

                bullet_layout = prs.slide_layouts[1]
                for s_info in slide_list:
                    s = prs.slides.add_slide(bullet_layout)
                    s.shapes.title.text = s_info.get("title", "Slide")
                    s.placeholders[1].text = s_info.get("content", "")

                prs.save(str(p))
                return {
                    "success": True,
                    "doc_type": "pptx",
                    "output_path": str(p),
                    "slides_count": len(prs.slides),
                    "message": f"Successfully created PowerPoint presentation ({len(prs.slides)} slides) at {p}",
                }

            else:
                # Fallback text
                p.write_text(content, encoding="utf-8")
                return {
                    "success": True,
                    "doc_type": "text",
                    "output_path": str(p),
                    "message": f"Created text file at {p}",
                }
        except Exception as e:
            return {"success": False, "error": str(e), "output_path": output_path}

    def convert(self, src_path: str, dest_path: str) -> Dict[str, Any]:
        """Convert documents between formats (e.g. CSV -> Excel, Text -> PDF/Word)."""
        try:
            src = self._resolve_path(src_path)
            dest = self._resolve_path(dest_path)
            if not src.exists():
                return {"success": False, "error": f"Source file not found: {src_path}"}

            src_ext = src.suffix.lower()
            dest_ext = dest.suffix.lower()

            # CSV to Excel
            if src_ext in (".csv", ".tsv") and dest_ext in (".xlsx", ".xls"):
                rows = []
                delimiter = "\t" if src_ext == ".tsv" else ","
                with open(src, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    for r in reader:
                        rows.append(r)
                return self.generate(
                    doc_type="xlsx",
                    output_path=str(dest),
                    title=src.stem,
                    table_data=rows,
                )

            # Excel to CSV
            elif src_ext in (".xlsx", ".xls") and dest_ext == ".csv":
                res = self.read(str(src))
                if not res.get("success"):
                    return res
                sheets = res.get("sheets", {})
                first_sheet = next(iter(sheets.values())) if sheets else []
                with open(dest, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    for r in first_sheet:
                        writer.writerow(r)
                return {
                    "success": True,
                    "output_path": str(dest),
                    "message": f"Converted Excel to CSV at {dest}",
                }

            # Text / Markdown to Word (.docx)
            elif src_ext in (".txt", ".md") and dest_ext == ".docx":
                content = src.read_text(encoding="utf-8", errors="replace")
                return self.generate(
                    doc_type="docx",
                    output_path=str(dest),
                    title=src.stem.replace("_", " ").title(),
                    content=content,
                )

            # Text / Markdown to PDF (.pdf)
            elif src_ext in (".txt", ".md") and dest_ext == ".pdf":
                content = src.read_text(encoding="utf-8", errors="replace")
                return self.generate(
                    doc_type="pdf",
                    output_path=str(dest),
                    title=src.stem.replace("_", " ").title(),
                    content=content,
                )

            else:
                return {
                    "success": False,
                    "error": f"Unsupported conversion from {src_ext} to {dest_ext}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
