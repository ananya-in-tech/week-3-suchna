"""Dates as Indian notices write them → real dates. Code does this, not the model.

"25.10.2026", "25/10/26", "25 अक्टूबर 2026", "२५-१०-२०२६", "Oct 25th", "within 7 days of this notice".
Numeric dates are day-first: 03.11.2026 is 3 November. The model sometimes flips that, so its
own reading is only a fallback when this parser finds nothing.
"""

import re
from datetime import date, timedelta

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    "जनवरी": 1, "फरवरी": 2, "फ़रवरी": 2, "मार्च": 3, "अप्रैल": 4, "अप्रेल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10,
    "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}
_MONTH = "|".join(sorted(map(re.escape, MONTHS), key=len, reverse=True))
_ORD = r"(?:st|nd|rd|th)?"

PATTERNS = [
    ("iso", re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")),
    ("dmy", re.compile(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})\b")),
    ("d_month", re.compile(rf"\b(\d{{1,2}}){_ORD}\s*(?:of\s+)?({_MONTH})\.?,?\s*(\d{{4}})?", re.I)),
    ("month_d", re.compile(rf"(?<![\wऀ-ॿ])({_MONTH})\.?\s+(\d{{1,2}}){_ORD}\b,?\s*(\d{{4}})?", re.I)),
    ("within", re.compile(r"(?:within|in)\s+(\d{1,3})\s+(?:working\s+)?days|(\d{1,3})\s+दिन(?:ों)?\s+(?:के\s+)?(?:भीतर|अंदर|अन्दर)",
                          re.I)),
]


def normalize(text: str) -> str:
    return (text or "").translate(_DEV_DIGITS)


def _make(y: int | None, m: int, d: int, ref: date) -> date | None:
    if y is not None and y < 100:
        y += 2000
    try:
        if y is None:  # "25 Oct": the coming one, unless it is only a little in the past
            got = date(ref.year, m, d)
            return got if got >= ref - timedelta(days=60) else date(ref.year + 1, m, d)
        return date(y, m, d)
    except ValueError:
        return None


def find_dates(text: str, ref: date) -> list[date]:
    """Every date in `text`, in reading order. `ref` is the notice date (for "within 7 days" and missing years)."""
    t = normalize(text)
    found: list[tuple[int, date]] = []
    taken: list[tuple[int, int]] = []
    for kind, pat in PATTERNS:
        for m in pat.finditer(t):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            g = m.groups()
            if kind == "iso":
                got = _make(int(g[0]), int(g[1]), int(g[2]), ref)
            elif kind == "dmy":
                got = _make(int(g[2]), int(g[1]), int(g[0]), ref)
            elif kind == "d_month":
                got = _make(int(g[2]) if g[2] else None, MONTHS[g[1].lower()], int(g[0]), ref)
            elif kind == "month_d":
                got = _make(int(g[2]) if g[2] else None, MONTHS[g[0].lower()], int(g[1]), ref)
            else:
                got = ref + timedelta(days=int(g[0] or g[1]))
            if got and date(2000, 1, 1) <= got <= date(2100, 1, 1):
                found.append((m.start(), got))
                taken.append((m.start(), m.end()))
    return [d for _, d in sorted(found, key=lambda x: x[0])]


def parse_iso(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def resolve(date_text: str | None, model_iso: str | None, ref: date, *, last: bool = True) -> tuple[date | None, str | None]:
    """Pick the date for one action or event. Ranges ("20.10 to 25.10") give the last day for a deadline,
    the first for an event. Returns (date, note) where note says when a person should double-check."""
    found = find_dates(date_text or "", ref)
    guess = parse_iso(model_iso)
    if found:  # the written date wins over the model's reading
        return (found[-1] if last else found[0]), None
    if guess:
        return guess, "date worked out by Gemma, please check"
    return None, None
