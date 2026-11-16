try:
    import pytesseract
    from PIL import Image
    _HAS_TESSERACT = True
except Exception:
    _HAS_TESSERACT = False


class OCRProcessor:
    def extract_text(self, image_path):
        if not _HAS_TESSERACT:
            return "OCR not available (install pytesseract)"
        img = Image.open(image_path)
        return pytesseract.image_to_string(img).strip()

    def extract_text_from_image(self, image):
        if not _HAS_TESSERACT:
            return "OCR not available (install pytesseract)"
        return pytesseract.image_to_string(image).strip()
