from datetime import datetime
from PIL import Image

_EXIF_TAG_DATETIME_ORIGINAL = 36867
_EXIF_FMT = "%Y:%m:%d %H:%M:%S"


def read_datetime_original(path) -> datetime | None:
    try:
        img = Image.open(path)
        exif = img.getexif()
        raw = exif.get(_EXIF_TAG_DATETIME_ORIGINAL)
        if not raw:
            return None
        return datetime.strptime(raw, _EXIF_FMT)
    except Exception:
        return None
