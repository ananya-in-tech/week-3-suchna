"""Hosted demo (DEMO=true): Render's free plan has 512 MB of RAM and Gemma needs several GB, so the hosted
Suchna can't read new notices. It ships with real Gemma readings of the SAMPLE notices in samples/ instead.

- Readings come from demo/seed.json, exported from a local run by scripts/export_demo.py.
- Each visitor's profile lives in their own cookie, so visitors never see or overwrite each other's.
- Uploads, ticks, overrides and deletes are off: nothing a visitor does is stored on the server.
- Dates are moved forward by the days since the export, so the deadlines stay in the future. The UI says so.
"""

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, unquote

from suchna.config import ROOT
from suchna.db import DB, PROFILE_KEYS

SEED = ROOT / "demo" / "seed.json"
FILES = ROOT / "demo" / "notices"
COOKIE = "suchna_profile"
DEFAULT_PROFILE = {"program": "B.Tech", "department": "Computer Science", "semester": 3, "hostel": True}


def export(db: DB, names: set[str], notice_dir: Path, exported_on: date) -> int:
    """Copy finished readings of the named files (and their files) into demo/."""
    FILES.mkdir(parents=True, exist_ok=True)
    out = []
    for n in sorted(db.notices(), key=lambda n: n["id"]):
        if n["status"] != "done" or n["original_name"] not in names:
            continue
        stem = n["file"].rsplit(".", 1)[0]
        for f in (n["file"], f"{stem}_preview.jpg"):
            shutil.copy2(notice_dir / f, FILES / f)
        items = [{k: it[k] for k in ("kind", "what", "due", "date_text", "date_note", "quote")} for it in db.items(n["id"])]
        out.append({k: v for k, v in n.items() if k not in ("id", "override", "status", "error")} | {"items": items})
    SEED.write_text(json.dumps({"exported_on": exported_on.isoformat(), "notices": out}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return len(out)


def _shift(iso: str | None, days: int) -> str | None:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat() if iso else None


def seed(db: DB, notice_dir: Path, today: date) -> int:
    """Load the demo readings into an empty database. Returns how many days the dates were moved."""
    data = json.loads(SEED.read_text(encoding="utf-8"))
    shift = max(0, (today - date.fromisoformat(data["exported_on"])).days)
    if db.notices():
        return shift
    notice_dir.mkdir(parents=True, exist_ok=True)
    for n in data["notices"]:
        stem = n["file"].rsplit(".", 1)[0]
        for f in (n["file"], f"{stem}_preview.jpg"):
            shutil.copy2(FILES / f, notice_dir / f)
        nid = db.add_notice(n["file"], n["original_name"], n["kind"])
        facts = {k: n[k] for k in ("title", "issued_by", "language", "summary", "audience")}
        facts["notice_date"] = _shift(n["notice_date"], shift)
        facts["items"] = [it | {"due": _shift(it["due"], shift)} for it in n["items"]]
        db.save_reading(nid, facts, text=n["text"], page_notes=n["page_notes"], pages_read=n["pages_read"],
                        pages_total=n["pages_total"], latency_ms=n["latency_ms"])
    return shift


def cookie_value(profile: dict) -> str:
    return quote(json.dumps(profile, ensure_ascii=False))  # JSON's quotes and commas aren't cookie-safe


def profile_from_cookie(raw: str | None) -> dict:
    try:
        data = json.loads(unquote(raw)) if raw else DEFAULT_PROFILE
    except ValueError:
        data = DEFAULT_PROFILE
    return {k: data.get(k) for k in PROFILE_KEYS} if isinstance(data, dict) else dict.fromkeys(PROFILE_KEYS)
