try:
    import docx
    _HAS_DOCX = True
except Exception:
    _HAS_DOCX = False


class DocxParser:
    def parse(self, path):
        if not _HAS_DOCX:
            return "DOCX parsing not available (install python-docx)"
        doc = docx.Document(path)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs).strip()
