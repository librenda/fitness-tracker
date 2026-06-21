from datetime import datetime
from PIL import Image

_EXIF_TAG_DATETIME_ORIGINAL = 36867  # lives in Exif sub-IFD (0x8769)
_EXIF_IFD_EXIF = 0x8769
_EXIF_TAG_DATETIME = 306             # IFD0 fallback
_EXIF_FMT = "%Y:%m:%d %H:%M:%S"


def read_datetime_original(path) -> datetime | None:
    try:
        img = Image.open(path)
        exif = img.getexif()
        raw = exif.get_ifd(_EXIF_IFD_EXIF).get(_EXIF_TAG_DATETIME_ORIGINAL)
        if not raw:
            raw = exif.get(_EXIF_TAG_DATETIME)
        if not raw:
            return None
        return datetime.strptime(raw, _EXIF_FMT)
    except Exception:
        return None
