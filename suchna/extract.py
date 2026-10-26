"""Notice file → pages Gemma can read: clean text where the PDF has a real text layer, page images otherwise.

Many Hindi university PDFs are typed in legacy fonts (Kruti Dev, DevLys, Chanakya). They look like
Hindi on screen, but the text layer is ASCII, e.g. "fo'ofo|ky; }kjk" for "विश्वविद्यालय द्वारा".
Feeding that to the model gives confident nonsense, so those pages are read as images instead.
"""

import io
import re
from dataclasses import dataclass

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MIN_TEXT_CHARS = 60
RENDER_DPI = 150

LEGACY_FONTS = ("kruti", "devlys", "chanakya", "walkman", "shusha", "akruti", "shivaji", "agra", "aman", "kundli")
# Very common Hindi words as they come out of a Kruti Dev text layer: है, का, के, की, कि, में, से, और, यह, तथा, लिए
LEGACY_WORDS = {"gS", "dk", "ds", "dh", "fd", "esa", "ls", "vkSj", ";g", "rFkk", "fy,", "gksxk", "fnukad"}
_ODD_INSIDE = re.compile(r"[A-Za-z][;'|}{\[\]\\~`][A-Za-z]|^[;'|}{\]\\~][A-Za-z]")


class BadFile(Exception):
    pass


@dataclass
class Page:
    number: int
    text: str | None = None     # usable text layer
    jpeg: bytes | None = None   # page image for Gemma vision
    note: str | None = None     # why we chose this path, shown in the UI


def looks_legacy(text: str, fonts: list[str] = ()) -> bool:
    """True if the text layer is legacy-font Hindi (ASCII that only looks Hindi in that font)."""
    if any(any(f in name.lower() for f in LEGACY_FONTS) for name in fonts):
        return True
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    if len(words) < 12:
        return False
    odd = sum(1 for w in words if w in LEGACY_WORDS or _ODD_INSIDE.search(w))
    return odd / len(words) > 0.12


def garbled_hindi(text: str) -> bool:
    """Unicode Hindi whose conjuncts came out as stray Latin glyphs ("विश्वविद्यालय" → "वə ȇ वə Ǿालय").
    Common when a PDF embeds a Devanagari font without a proper ToUnicode map."""
    deva = sum(1 for c in text if "ऀ" <= c <= "ॿ")
    if deva < 20:
        return False
    odd = sum(1 for c in text if c.isalpha() and not c.isascii() and not "ऀ" <= c <= "ॿ")
    return odd / deva > 0.01


def usable_text(text: str) -> bool:
    t = text.strip()
    if len(t) < MIN_TEXT_CHARS:
        return False
    junk = t.count("�") + t.count("(cid:")
    return junk / len(t) < 0.02


def clean_image(img: Image.Image) -> bytes:
    """Fresh RGB copy (no EXIF, no location), sized for the model, with a mild contrast lift for phone photos."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    clean = Image.new("RGB", img.size)
    clean.paste(ImageOps.autocontrast(img, cutoff=1))
    out = io.BytesIO()
    clean.save(out, "JPEG", quality=88)
    return out.getvalue()


def _render(page, dpi: int) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def from_image(raw: bytes) -> list[Page]:
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise BadFile("That file isn't an image or PDF Suchna can read.") from e
    return [Page(1, jpeg=clean_image(img), note="photo, read by Gemma vision")]


def from_pdf(raw: bytes, max_pages: int) -> tuple[list[Page], int]:
    try:
        doc = pymupdf.open(stream=raw, filetype="pdf")
    except Exception as e:
        raise BadFile("That PDF couldn't be opened.") from e
    if doc.needs_pass:
        raise BadFile("That PDF is password-protected.")
    pages = []
    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        text = page.get_text("text", sort=True)
        fonts = [f[3] for f in page.get_fonts()]
        legacy, garbled = looks_legacy(text, fonts), garbled_hindi(text)
        if usable_text(text) and not legacy and not garbled:
            pages.append(Page(i + 1, text=text.strip(), note="text layer"))
            continue
        img = _render(page, RENDER_DPI)
        why = ("legacy Hindi font in the PDF" if legacy else "garbled Hindi text layer" if garbled
               else "scanned page")
        pages.append(Page(i + 1, jpeg=clean_image(img), note=f"{why}, read by Gemma vision"))
    total = doc.page_count
    doc.close()
    if not pages:
        raise BadFile("That PDF has no pages.")
    return pages, total


def read_file(raw: bytes, filename: str, max_pages: int = 3) -> tuple[str, list[Page], int]:
    """Returns (kind, pages, total_pages)."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise BadFile("That file is too large (max 25 MB).")
    if raw[:5] == b"%PDF-" or filename.lower().endswith(".pdf"):
        pages, total = from_pdf(raw, max_pages)
        return "pdf", pages, total
    return "image", from_image(raw), 1


def preview(raw: bytes, kind: str) -> bytes:
    """First page as a JPEG for the notice screen."""
    if kind == "image":
        return clean_image(Image.open(io.BytesIO(raw)))
    with pymupdf.open(stream=raw, filetype="pdf") as doc:
        return clean_image(_render(doc[0], 110))
