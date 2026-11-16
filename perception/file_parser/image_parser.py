try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


class ImageParser:
    def describe(self, path):
        if not _HAS_PIL:
            return {"error": "PIL not available (install Pillow)"}
        img = Image.open(path)
        info = {
            "size": img.size,
            "format": img.format,
            "mode": img.mode,
        }
        exif_data = img._getexif()
        if exif_data:
            exif = {}
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = str(value)
                exif[tag] = value
            info["exif"] = exif
        return info
