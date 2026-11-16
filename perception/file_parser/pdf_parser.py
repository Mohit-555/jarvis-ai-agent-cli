try:
    import fitz
    _HAS_FITZ = True
except Exception:
    _HAS_FITZ = False

try:
    from pdfminer.high_level import extract_text as pdfminer_extract
    _HAS_PDFMINER = True
except Exception:
    _HAS_PDFMINER = False


class PDFParser:
    def parse(self, path):
        if _HAS_FITZ:
            doc = fitz.open(path)
            text = "".join(page.get_text() for page in doc)
            doc.close()
            return text.strip()
        if _HAS_PDFMINER:
            return pdfminer_extract(path).strip()
        return "PDF parsing not available (install PyMuPDF or pdfminer)"

    def parse_pages(self, path):
        if _HAS_FITZ:
            doc = fitz.open(path)
            pages = [page.get_text() for page in doc]
            doc.close()
            return [p.strip() for p in pages if p.strip()]
        if _HAS_PDFMINER:
            text = pdfminer_extract(path).strip()
            return [text]
        return ["PDF parsing not available (install PyMuPDF or pdfminer)"]
