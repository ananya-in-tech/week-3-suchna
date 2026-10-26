"""Cover image for the DEV post: a pinned Hindi notice → Suchna's English answer card.

    .venv/Scripts/python scripts/make_cover.py   → imgs/cover.png (2000×840, DEV's 1000×420 at 2×)

Text goes through PyMuPDF's HTML layout, which shapes Devanagari properly (PIL alone breaks the conjuncts).
"""

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "imgs" / "cover.png"
W, H, S = 1000, 420, 2  # design size in px, rendered at S×

INDIGO, INDIGO_2, PAPER, CARD = (36, 48, 107), (48, 62, 132), (250, 248, 242), (255, 254, 251)
YES, YES_SOFT, HI, PIN, INK = (47, 125, 79), (225, 240, 230), (255, 230, 128), (217, 71, 43), (29, 35, 64)

FONTS = pymupdf.Archive("C:/Windows/Fonts")
CSS = """
@font-face { font-family: serif; src: url(georgiab.ttf); }
@font-face { font-family: sans; src: url(segoeui.ttf); }
@font-face { font-family: sans; src: url(segoeuib.ttf); font-weight: bold; }
* { margin: 0; padding: 0; }
body { font-family: sans; color: #1d2340; }
.serif { font-family: serif; }
"""


def text(html: str, w: int, css: str = "") -> Image.Image:
    """HTML laid out w design px wide → transparent RGBA image cropped to the ink, so (x, y) places the text's top."""
    doc = pymupdf.open()
    page = doc.new_page(width=w, height=800)
    spare, _ = page.insert_htmlbox(page.rect, html, css=CSS + css, archive=FONTS, scale_low=1)  # never shrink to fit
    if spare < 0:
        raise ValueError(f"text too long for {w} px: {html[:60]!r}")
    pix = page.get_pixmap(matrix=pymupdf.Matrix(S, S), alpha=True)
    img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    _, top, _, bottom = img.getchannel("A").getbbox()
    return img.crop((0, top, img.width, bottom))


def box(w: int, h: int, fill, radius: int = 14, outline=None, width: int = 0) -> Image.Image:
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius * S, fill=fill, outline=outline, width=width * S)
    return img


def shadow(img: Image.Image, blur: int = 14, alpha: int = 90) -> Image.Image:
    pad = blur * 3
    sh = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    mask = img.getchannel("A").point(lambda a: alpha if a else 0)
    sh.paste((8, 12, 40, 255), (pad, pad), mask)
    return sh.filter(ImageFilter.GaussianBlur(blur))


def place(canvas: Image.Image, img: Image.Image, x: float, y: float, with_shadow: bool = False) -> None:
    if with_shadow:
        sh = shadow(img)
        pad = (sh.width - img.width) // 2
        canvas.alpha_composite(sh, (int(x * S) - pad + 6 * S, int(y * S) - pad + 10 * S))
    canvas.alpha_composite(img, (int(x * S), int(y * S)))


def centered(img: Image.Image, w: int, h: int, dy: float = 0) -> tuple[int, int]:
    """Offset (scaled px) that centres `img` in a w×h design-px box."""
    return (w * S - img.width) // 2, int((h * S - img.height) / 2 + dy * S)


def notice() -> Image.Image:
    """A printed Hindi notice, the deadline marked with a highlighter, pinned at the top."""
    w, h = 230, 300
    paper = box(w, h, PAPER, radius=3)
    y = 30
    for html in (
        '<p style="text-align:center; font-size:13px; font-weight:bold">नमूना विश्वविद्यालय</p>',
        '<p style="text-align:center; font-size:9px; color:#4c5373">परीक्षा नियंत्रक कार्यालय</p>',
        '<p style="font-size:8px; color:#4c5373">पत्रांक: परीक्षा/2026/418 &nbsp;&nbsp;&nbsp; दिनांक: 16.10.2026</p>',
        '<p style="text-align:center; font-size:12px; font-weight:bold; text-decoration:underline">सूचना</p>',
        '<p style="font-size:9.5px; line-height:1.6">बी.टेक तृतीय एवं पंचम सेमेस्टर के सभी छात्र-छात्राओं को सूचित किया जाता है कि '
        'विषम सेमेस्टर परीक्षा 2026 हेतु परीक्षा फॉर्म ऑनलाइन पोर्टल पर <b style="background-color:#ffe680">दिनांक 28.10.2026 तक</b> '
        'भरे जा सकते हैं। परीक्षा शुल्क ₹1500 है।</p>',
        '<p style="font-size:9.5px; line-height:1.6">विलंब शुल्क ₹500 के साथ फॉर्म 02.11.2026 तक स्वीकार किए जाएंगे। '
        'भरे हुए फॉर्म की प्रति, शुल्क रसीद के साथ, विभाग कार्यालय में जमा करें।</p>',
        '<p style="font-size:9px; text-align:right">परीक्षा नियंत्रक</p>',
    ):
        t = text(html, w - 36)
        paper.alpha_composite(t, (18 * S, int(y * S)))
        y += t.height / S + 9
    pin = Image.new("RGBA", (24 * S, 24 * S), (0, 0, 0, 0))
    ImageDraw.Draw(pin).ellipse((2 * S, 2 * S, 20 * S, 20 * S), fill=PIN)
    ImageDraw.Draw(pin).ellipse((6 * S, 5 * S, 11 * S, 10 * S), fill=(255, 170, 150))
    paper.alpha_composite(pin, ((w // 2 - 11) * S, 3 * S))
    return paper.rotate(-5, resample=Image.BICUBIC, expand=True)


def answer() -> Image.Image:
    w, h = 300, 262
    card = box(w, h, CARD, radius=16)
    head = box(w - 24, 80, YES_SOFT, radius=12, outline=YES, width=2)
    head.alpha_composite(text('<p class="serif" style="font-size:20px; color:#2f7d4f">Yes, this affects you</p>', w - 52), (14 * S, 16 * S))
    head.alpha_composite(text('<p style="font-size:12px; color:#2f4a3a; line-height:1.35">It\'s for B.Tech semester 3, 5,<br>'
                              'and you\'re in semester 3.</p>', w - 52), (14 * S, 44 * S))
    card.alpha_composite(head, (12 * S, 12 * S))
    card.alpha_composite(text('<p class="serif" style="font-size:14px">What to do</p>', 200), (16 * S, 108 * S))

    def todo(y: int, what: str, big: str, small: str, soon: bool) -> None:
        due = box(60, 50, HI if soon else (255, 246, 204), radius=9)
        num = text(f'<p class="serif" style="text-align:center; font-size:22px">{big}</p>', 60)
        sub = text(f'<p style="text-align:center; font-size:9.5px; color:#4c5373">{small}</p>', 60)
        due.alpha_composite(num, (0, 8 * S))
        due.alpha_composite(sub, (0, 34 * S))
        card.alpha_composite(due, (14 * S, y * S))
        t = text(f'<p style="font-size:13px; font-weight:bold; line-height:1.3">{what}</p>', w - 104)
        card.alpha_composite(t, (88 * S, y * S + centered(t, 1, 50)[1]))

    todo(130, "Fill the exam form online", "2", "days · 28 Oct", True)
    todo(190, "Submit form + fee receipt at the department", "9", "days · 4 Nov", False)
    return card


def arrow() -> Image.Image:
    img = Image.new("RGBA", (54 * S, 30 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line((4 * S, 15 * S, 40 * S, 15 * S), fill=HI, width=4 * S)
    d.polygon([(38 * S, 5 * S), (52 * S, 15 * S), (38 * S, 25 * S)], fill=HI)
    return img


def main() -> None:
    canvas = Image.new("RGBA", (W * S, H * S), INDIGO + (255,))
    d = ImageDraw.Draw(canvas)
    for x in range(0, W, 22):  # faint notice-board dots
        for y in range(0, H, 22):
            d.ellipse(((x + 11) * S - 2, (y + 11) * S - 2, (x + 11) * S + 2, (y + 11) * S + 2), fill=INDIGO_2)

    y = 52
    for html, gap in (
        ('<p class="serif" style="font-size:56px; color:#ffffff">Suchna</p>', 14),
        ('<p style="font-size:21px; color:#a9b4f0">सूचना · the notice</p>', 30),
        ('<p class="serif" style="font-size:26px; color:#ffffff; line-height:1.3">Does this affect me?<br>What do I do?<br>By when?</p>', 26),
        ('<p style="font-size:14.5px; color:#cfd5f5; line-height:1.45">Hindi or English notices in, plain English answers out.<br>'
         'Read by Gemma 4 on my laptop. Nothing uploaded.</p>', 24),
    ):
        t = text(html, 380)
        place(canvas, t, 44, y)
        y += t.height / S + gap

    x = 44
    for label, fill in (("Slow and steady", HI), ("Open-source AI · offline", (230, 232, 244))):
        t = text(f'<p style="font-size:12.5px; font-weight:bold; color:#24306b">{label}</p>', 260)
        t = t.crop((0, 0, t.getbbox()[2], t.height))
        chip = box(t.width // S + 26, 28, fill, radius=14)
        chip.alpha_composite(t, centered(t, t.width // S + 26, 28))
        place(canvas, chip, x, y)
        x += chip.width / S + 10

    place(canvas, notice(), 398, 40, with_shadow=True)
    place(canvas, arrow(), 640, 196)
    place(canvas, answer(), 688, 80, with_shadow=True)

    OUT.parent.mkdir(exist_ok=True)
    canvas.convert("RGB").save(OUT, optimize=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
