"""Deadlines → an .ics file any calendar app imports. All-day events with a reminder the day before."""

from datetime import date, datetime, timedelta, UTC


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode()) > 74:
            out.append(cur)
            cur = " "
        cur += ch
    return "\r\n".join(out + [cur])


def calendar(entries: list[dict]) -> str:
    """entries: {"uid", "due" (YYYY-MM-DD), "summary", "description"}."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Suchna//Notice deadlines//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Suchna deadlines"]
    for e in entries:
        day = date.fromisoformat(e["due"])
        lines += ["BEGIN:VEVENT", f"UID:{e['uid']}@suchna.local", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{_esc(e['summary'])}", f"DESCRIPTION:{_esc(e.get('description') or '')}",
                  "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(e['summary'])}", "TRIGGER:-PT15H", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
