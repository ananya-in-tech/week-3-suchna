"""Make SAMPLE notices for testing (not real notices; each one says so in its footer).

    .venv/Scripts/python scripts/make_samples.py   → samples/*.pdf, samples/*.jpg
"""

import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "samples"
FOOT = "<p class='foot'>SAMPLE NOTICE made for testing Suchna. Not a real university notice.</p>"
CSS = """
* { font-family: sans-serif; }
body { font-size: 11pt; line-height: 1.5; }
h1 { font-size: 15pt; text-align: center; margin: 0; }
h2 { font-size: 12pt; text-align: center; margin: 4pt 0 12pt; text-decoration: underline; }
.meta { display: flex; justify-content: space-between; }
.right { text-align: right; }
.foot { font-size: 8pt; color: #888; margin-top: 30pt; text-align: center; }
table { border-collapse: collapse; } td, th { border: 1px solid #333; padding: 3pt 8pt; }
"""

NOTICES = {
    "hindi_exam_form": """
<h1>नमूना विश्वविद्यालय, डेमो नगर</h1>
<p style="text-align:center">परीक्षा नियंत्रक कार्यालय</p>
<p>पत्रांक: परीक्षा/2026/418 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; दिनांक: 16.10.2026</p>
<h2>सूचना</h2>
<p>बी.टेक तृतीय एवं पंचम सेमेस्टर के सभी छात्र-छात्राओं को सूचित किया जाता है कि विषम सेमेस्टर परीक्षा 2026 हेतु
परीक्षा फॉर्म ऑनलाइन पोर्टल पर दिनांक 28.10.2026 तक भरे जा सकते हैं। परीक्षा शुल्क ₹1500 है।</p>
<p>विलंब शुल्क ₹500 के साथ फॉर्म 02.11.2026 तक स्वीकार किए जाएंगे। इसके बाद कोई फॉर्म स्वीकार नहीं किया जाएगा।</p>
<p>भरे हुए फॉर्म की प्रति, शुल्क रसीद के साथ, अपने विभाग कार्यालय में 04.11.2026 तक जमा करें।</p>
<p>परीक्षाएं 20 नवम्बर 2026 से प्रारंभ होंगी। विस्तृत समय-सारणी अलग से जारी की जाएगी।</p>
<p class="right">परीक्षा नियंत्रक</p>
""",
    "english_hostel_fee": """
<h1>Sample University, Demo Nagar</h1>
<p style="text-align:center">Office of the Chief Warden</p>
<p>No. CW/2026/77 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Dated: 19/10/2026</p>
<h2>NOTICE: Hostel fee for the even semester</h2>
<p>All hostel residents are informed that the hostel and mess fee for the even semester (January to May 2027)
is ₹28,500. It must be paid through the university fee portal by 15th November, 2026.</p>
<p>Residents who wish to vacate the hostel must submit the room surrender form to their warden by 10.11.2026.</p>
<p>A late fine of ₹50 per day will be charged after the last date. Rooms of residents who have not paid by
30 November 2026 will be allotted to students on the waiting list.</p>
<p class="right">Chief Warden</p>
""",
    "hindi_holiday_photo": """
<h1>नमूना विश्वविद्यालय, डेमो नगर</h1>
<p style="text-align:center">कुलसचिव कार्यालय</p>
<p>दिनांक: 21.10.2026</p>
<h2>अवकाश सूचना</h2>
<p>विश्वविद्यालय के सभी छात्र-छात्राओं एवं कर्मचारियों को सूचित किया जाता है कि दीपावली के अवसर पर
दिनांक 07.11.2026 से 11.11.2026 तक विश्वविद्यालय बंद रहेगा।</p>
<p>दिनांक 12.11.2026 से कक्षाएं सामान्य रूप से संचालित होंगी।</p>
<p class="right">कुलसचिव</p>
""",
    "bilingual_scholarship_scan": """
<h1>नमूना विश्वविद्यालय / Sample University</h1>
<p>दिनांक / Date: 14.10.2026</p>
<h2>छात्रवृत्ति सत्यापन / Scholarship verification</h2>
<p>राज्य छात्रवृत्ति योजना के अंतर्गत आवेदन करने वाले बी.ए., बी.एससी. एवं बी.कॉम. के सभी छात्र अपने मूल दस्तावेज़
(आधार कार्ड, आय प्रमाण पत्र, पिछली अंकतालिका) के साथ सत्यापन हेतु छात्रवृत्ति प्रकोष्ठ, कक्ष 12 में उपस्थित हों।</p>
<p>Students of BA, B.Sc and B.Com who have applied for the State Scholarship must come to the Scholarship Cell,
Room 12, with original documents for verification.</p>
<table><tr><th>दिनांक / Date</th><th>पाठ्यक्रम / Course</th></tr>
<tr><td>27.10.2026</td><td>B.A.</td></tr><tr><td>28.10.2026</td><td>B.Sc.</td></tr><tr><td>29.10.2026</td><td>B.Com.</td></tr></table>
<p>सत्यापन न कराने पर छात्रवृत्ति आवेदन निरस्त कर दिया जाएगा। / Applications not verified will be cancelled.</p>
<p class="right">समन्वयक, छात्रवृत्ति प्रकोष्ठ / Coordinator</p>
""",
}


def html_pdf(body: str) -> bytes:
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    story = pymupdf.Story(html=f"<body>{body}{FOOT}</body>", user_css=CSS)
    rect = pymupdf.paper_rect("a4") + (50, 50, -50, -50)
    more = True
    while more:
        dev = writer.begin_page(pymupdf.paper_rect("a4"))
        more, _ = story.place(rect)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()


def as_photo(pdf: bytes, seed: int) -> Image.Image:
    """Render like a slightly tilted, soft phone photo of a printed notice on a board."""
    rnd = random.Random(seed)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pix = doc[0].get_pixmap(dpi=130, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    img = img.rotate(rnd.uniform(-2.5, 2.5), expand=True, fillcolor=(196, 170, 130))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    tint = Image.new("RGB", img.size, (250, 240, 215))
    return Image.blend(img, tint, 0.12)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, body in NOTICES.items():
        pdf = html_pdf(body)
        if name.endswith("_photo"):
            as_photo(pdf, 1).save(OUT / f"{name}.jpg", quality=85)
        elif name.endswith("_scan"):  # image-only PDF: no text layer, like a scanner's output
            img = as_photo(pdf, 2).convert("L")
            doc = pymupdf.open()
            page = doc.new_page(width=595, height=842)
            b = io.BytesIO()
            img.save(b, "JPEG", quality=80)
            page.insert_image(page.rect, stream=b.getvalue())
            doc.save(OUT / f"{name}.pdf")
        else:
            (OUT / f"{name}.pdf").write_bytes(pdf)
        print("made", name)


if __name__ == "__main__":
    main()
