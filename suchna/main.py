"""Suchna: university notices in Hindi or English → "Does this affect me? What do I do, and by when?" in English.
Drop the PDF or photo and walk away; Gemma reads it on this computer, one notice at a time."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

import json

from fastapi import Cookie, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from suchna import ai, demo, extract, ics, match, reader
from suchna.config import ROOT, check_privacy, get_settings
from suchna.db import DB

log = logging.getLogger("suchna")
_db: DB | None = None
_shift_days = 0  # demo only: how far the sample dates were moved forward
_wake: asyncio.Event | None = None  # made in lifespan, on the server's event loop
INBOX_EVERY_SECONDS = 20
ALLOWED = {".pdf": "pdf", ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image"}


def db() -> DB:
    global _db
    if _db is None:
        _db = DB(get_settings().db_path)
    return _db


def set_db(new: DB) -> None:
    global _db
    _db = new


def notice_dir():
    d = get_settings().data_dir / "notices"
    d.mkdir(parents=True, exist_ok=True)
    return d


def inbox_dir():
    d = get_settings().data_dir / "inbox"
    d.mkdir(parents=True, exist_ok=True)
    return d


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


# --- the reading queue --------------------------------------------------------------------------

def store(raw: bytes, name: str) -> int:
    """Save a copy and a preview, queue it. Raises extract.BadFile."""
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    kind = "pdf" if raw[:5] == b"%PDF-" else ALLOWED.get(suffix)
    if not kind:
        raise extract.BadFile("Send a PDF or a photo (JPG, PNG, WEBP).")
    if len(raw) > extract.MAX_UPLOAD_BYTES:
        raise extract.BadFile("That file is too large (max 25 MB).")
    try:
        preview = extract.preview(raw, kind)
    except Exception as e:
        raise extract.BadFile("That file couldn't be opened. Is it a real PDF or photo?") from e
    stem = f"notice_{secrets.token_hex(8)}"
    file = stem + (".pdf" if kind == "pdf" else ".jpg")
    # photos are kept re-encoded (no EXIF/location); PDFs as they came
    (notice_dir() / file).write_bytes(raw if kind == "pdf" else preview)
    (notice_dir() / f"{stem}_preview.jpg").write_bytes(preview)
    return db().add_notice(file, name[:120], kind)


async def read_one(n: dict) -> None:
    s = get_settings()
    db().set_status(n["id"], "reading")
    try:
        raw = (notice_dir() / n["file"]).read_bytes()
        kind, pages, total = await asyncio.to_thread(extract.read_file, raw, n["file"], s.max_pages)
        raw_notice, ms = await reader.read_notice(pages)
    except extract.BadFile as e:
        db().set_status(n["id"], "failed", str(e))
        return
    except ai.AiUnavailable as e:
        log.warning("Notice %s not read: %s", n["id"], e)
        db().log_ai(0, False, 0, 0)
        msg = "Ollama isn't running. Start it and press Read again." if "Connect" in str(e) else \
            "Gemma couldn't read this one. Try a clearer photo, or press Read again."
        db().set_status(n["id"], "failed", msg)
        return
    vision = sum(1 for p in pages if p.jpeg)
    db().log_ai(ms, True, len(pages), vision)
    facts = reader.tidy(raw_notice, date.fromisoformat(n["created_at"][:10]))
    text = "\n".join(p.text for p in pages if p.text) or None
    db().save_reading(n["id"], facts, text=text, page_notes=[f"Page {p.number}: {p.note}" for p in pages],
                      pages_read=len(pages), pages_total=total, latency_ms=ms)


def sweep_inbox() -> int:
    """Files saved into data/inbox/ (say, from WhatsApp Desktop) get queued and moved out of the inbox."""
    added = 0
    for f in sorted(inbox_dir().iterdir()):
        if not f.is_file() or f.suffix.lower() not in ALLOWED:
            continue
        try:
            store(f.read_bytes(), f.name)
            added += 1
        except extract.BadFile as e:
            log.warning("Skipped %s: %s", f.name, e)
        f.unlink(missing_ok=True)
    return added


def wake() -> None:
    if _wake is not None:
        _wake.set()


async def worker() -> None:
    while True:
        _wake.clear()  # before looking, so an upload during a read isn't missed
        try:
            await asyncio.to_thread(sweep_inbox)
            while (n := db().next_queued()) is not None:
                await read_one(n)
        except Exception:
            log.exception("Reading queue hiccup")
        try:
            await asyncio.wait_for(_wake.wait(), timeout=INBOX_EVERY_SECONDS)
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    check_privacy(s)
    db()
    if s.demo:
        global _shift_days
        _shift_days = demo.seed(db(), notice_dir(), today())
    global _wake
    _wake = asyncio.Event()
    task = asyncio.create_task(worker())
    if s.ai_enabled and s.ai_warmup:
        async def warm():
            try:
                await ai.chat([{"role": "user", "content": "ok"}], num_predict=1)
            except ai.AiUnavailable as e:
                log.warning("Warm-up skipped: %s", e)
        asyncio.create_task(warm())
    yield
    task.cancel()


app = FastAPI(title="Suchna", version="0.1.0", lifespan=lifespan)


# --- models ---------------------------------------------------------------------------------------

class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, max_length=80)
    roll_no: str | None = Field(None, max_length=30)
    university: str | None = Field(None, max_length=120)
    program: str | None = Field(None, max_length=40)
    department: str | None = Field(None, max_length=80)
    semester: int | None = Field(None, ge=1, le=12)
    hostel: bool | None = None


class NoticePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    override: str | None = Field(None, pattern=r"^(yes|no)$")


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    done: bool


# --- helpers --------------------------------------------------------------------------------------

DEMO_ONLY = "This is the hosted demo, so it can't change anything. Run Suchna on your own computer to read your notices."


def no_demo() -> None:
    if get_settings().demo:
        raise HTTPException(403, DEMO_ONLY)


def profile_for(cookie: str | None) -> dict:
    """Locally: the one saved profile. In the demo: this visitor's own, from their cookie."""
    return demo.profile_from_cookie(cookie) if get_settings().demo else db().profile()

def _notice_or_404(nid: int) -> dict:
    n = db().notice(nid)
    if not n:
        raise HTTPException(404, "Notice not found")
    return n


def _clean(v: str | None) -> str | None:
    v = " ".join((v or "").split())
    return v or None


def days_left(due: str | None, ref: date) -> int | None:
    return (date.fromisoformat(due) - ref).days if due else None


def view(n: dict, profile: dict, items: list[dict], ref: date) -> dict:
    """A notice as the UI shows it: the verdict, and its items with days left."""
    out = {k: v for k, v in n.items() if k != "file"}
    out["verdict"] = match.verdict(n["audience"], profile, text=n["text"], override=n["override"]) if n["status"] == "done" else None
    out["items"] = [it | {"days_left": days_left(it["due"], ref)} for it in items]
    open_actions = [it for it in out["items"] if it["kind"] == "action" and not it["done"]]
    upcoming = [it for it in open_actions if it["due"] and it["days_left"] >= 0]
    out["next"] = min(upcoming, key=lambda it: it["due"]) if upcoming else None
    out["open_actions"] = len(open_actions)
    return out


# --- routes ---------------------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    queue = [n["status"] for n in db().notices()]
    s = get_settings()
    return {"ok": True, "ai": await ai.health(), "today": today().isoformat(),
            "queued": queue.count("queued"), "reading": queue.count("reading"),
            "demo": {"shift_days": _shift_days, "repo": s.repo_url} if s.demo else None}


@app.get("/api/profile")
def get_profile(suchna_profile: str | None = Cookie(None)):
    return profile_for(suchna_profile)


@app.put("/api/profile")
def put_profile(p: ProfileIn):
    data = p.model_dump()
    for k in ("name", "roll_no", "university", "program", "department"):
        data[k] = _clean(data[k])
    if not get_settings().demo:
        return db().save_profile(data)
    resp = Response(json.dumps(data, ensure_ascii=False), media_type="application/json")
    resp.set_cookie(demo.COOKIE, demo.cookie_value(data), max_age=30 * 86400, httponly=True, samesite="lax")
    return resp


@app.post("/api/notices", status_code=201)
async def upload(files: list[UploadFile] = File(...)):
    no_demo()
    if len(files) > 20:
        raise HTTPException(400, "Up to 20 notices at a time.")
    ids, errors = [], []
    for f in files:
        raw = await f.read()
        try:
            ids.append(await asyncio.to_thread(store, raw, f.filename or "notice"))
        except extract.BadFile as e:
            errors.append(f"{f.filename}: {e}")
    if not ids:
        raise HTTPException(400, "; ".join(errors) or "No file received.")
    wake()
    return {"ids": ids, "errors": errors}


@app.get("/api/notices")
def list_notices(suchna_profile: str | None = Cookie(None)):
    profile, ref = profile_for(suchna_profile), today()
    by_notice: dict[int, list] = {}
    for it in db().items():
        by_notice.setdefault(it["notice_id"], []).append(it)
    return {"today": ref.isoformat(), "profile_set": any(profile.get(k) for k in ("program", "semester", "department")),
            "notices": [view(n, profile, by_notice.get(n["id"], []), ref) for n in db().notices()]}


@app.get("/api/notices/{nid}")
def get_notice(nid: int, suchna_profile: str | None = Cookie(None)):
    n = _notice_or_404(nid)
    return view(n, profile_for(suchna_profile), db().items(nid), today()) | {"today": today().isoformat()}


@app.get("/api/notices/{nid}/preview.jpg")
def notice_preview(nid: int):
    n = _notice_or_404(nid)
    return FileResponse(notice_dir() / (n["file"].rsplit(".", 1)[0] + "_preview.jpg"), media_type="image/jpeg")


@app.get("/api/notices/{nid}/file")
def notice_file(nid: int):
    n = _notice_or_404(nid)
    media = "application/pdf" if n["kind"] == "pdf" else "image/jpeg"
    return FileResponse(notice_dir() / n["file"], media_type=media, filename=n["original_name"],
                        content_disposition_type="inline")


@app.post("/api/notices/{nid}/read")
def reread(nid: int):
    no_demo()
    n = _notice_or_404(nid)
    if n["status"] in ("queued", "reading"):
        raise HTTPException(409, "Already in the queue.")
    db().requeue(nid)
    wake()
    return {"ok": True}


@app.patch("/api/notices/{nid}")
def patch_notice(nid: int, p: NoticePatch):
    no_demo()
    _notice_or_404(nid)
    db().set_override(nid, p.override)
    return get_notice(nid, None)


@app.delete("/api/notices/{nid}", status_code=204)
def delete_notice(nid: int):
    no_demo()
    n = _notice_or_404(nid)
    if n["status"] == "reading":
        raise HTTPException(409, "Gemma is reading this one right now. Try again in a minute.")
    db().delete_notice(nid)
    stem = n["file"].rsplit(".", 1)[0]
    for f in (n["file"], f"{stem}_preview.jpg"):
        (notice_dir() / f).unlink(missing_ok=True)
    return Response(status_code=204)


@app.patch("/api/items/{iid}")
def patch_item(iid: int, p: ItemPatch):
    no_demo()
    if not db().item(iid):
        raise HTTPException(404, "Item not found")
    db().set_done(iid, p.done)
    return db().item(iid)


def _mine(profile: dict) -> list[tuple[dict, dict]]:
    """(notice, item) for every dated item in notices that affect you (yes or maybe)."""
    notices = {n["id"]: n for n in db().notices() if n["status"] == "done"}
    keep = {nid for nid, n in notices.items()
            if match.verdict(n["audience"], profile, text=n["text"], override=n["override"])["answer"] != "no"}
    return [(notices[it["notice_id"]], it) for it in db().items() if it["notice_id"] in keep]


@app.get("/api/calendar.ics")
def calendar(suchna_profile: str | None = Cookie(None)):
    entries = [{"uid": f"item-{it['id']}", "due": it["due"],
                "summary": ("Due: " if it["kind"] == "action" else "") + it["what"],
                "description": f"{n['title']}\n{it['quote'] or ''}"}
               for n, it in _mine(profile_for(suchna_profile)) if it["due"] and not it["done"]]
    return Response(ics.calendar(entries), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="suchna-deadlines.ics"'})


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
