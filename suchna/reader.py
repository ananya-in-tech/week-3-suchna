"""Notice pages → facts in English. Gemma reads (Hindi or English, text or scan); code checks the rest.

The model never sees your profile. It only says who the notice is for, what to do and by when, with
the original words as proof.

Slow and steady: a page image is first only transcribed, then the facts are pulled from that text. Asked to do
both at once from a photo, Gemma E2B quoted the Hindi perfectly but made up the title and who it was for. Whether it affects you is decided in `match.py`, so editing your profile
re-sorts every notice instantly, without another model call.
"""

import base64
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from suchna import ai, dates
from suchna.extract import Page

MAX_TEXT_CHARS = 9000


class RawAudience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    everyone: bool
    programs: list[str] = Field(max_length=12)
    semesters: list[int] = Field(max_length=10)
    years: list[int] = Field(max_length=6)
    departments: list[str] = Field(max_length=12)
    hostel_only: bool
    lists_specific_students: bool
    conditions: list[str] = Field(max_length=6)
    quote: str | None = Field(None, max_length=400)


class RawItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["action", "event"]
    what: str = Field(max_length=200)
    date_text: str | None = Field(None, max_length=120)
    date_iso: str | None = Field(None, max_length=20)
    quote: str | None = Field(None, max_length=400)


class RawNotice(BaseModel):
    """Exactly what the model may return."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=160)
    issued_by: str | None = Field(None, max_length=160)
    notice_date_text: str | None = Field(None, max_length=60)
    notice_date_iso: str | None = Field(None, max_length=20)
    language: Literal["hindi", "english", "mixed"]
    summary: str = Field(max_length=600)
    audience: RawAudience
    items: list[RawItem] = Field(max_length=14)


PROMPT = """You are reading an official notice from an Indian university or college. It may be in Hindi, English, or both.
Answer in English for a student who does not want to read the whole notice. Copy quotes in the notice's own language and script.

Return:
- title: a short English title (e.g. "Exam form submission for odd semester").
- issued_by: the office that issued it, translated to English (e.g. "Controller of Examinations"), or null.
- notice_date_text: the notice's own date exactly as written (often after "Date", "दिनांक" or "Dated"), or null. notice_date_iso: that date as YYYY-MM-DD. Indian dates are day first: 03.11.2026 is 2026-11-03.
- language: hindi, english or mixed.
- summary: one or two plain English sentences saying what the notice is about.
- audience: who must act on it.
  - everyone: true only if it is for all students, with no course, semester or department named.
  - programs: the courses named, in short English form, e.g. "B.Tech", "BA", "M.Sc", "PhD", or "UG" / "PG" for all undergraduate / postgraduate students.
  - semesters: only the semesters whose students must act (e.g. "students of third semester", "तृतीय सेमेस्टर के छात्र" -> 3).
    A semester the notice is about is not an audience: "hostel fee for the even semester" or "odd semester exams" say
    nothing about who must act, so leave semesters empty then.
  - years: year numbers of the students who must act (e.g. "2nd year students", "द्वितीय वर्ष" -> 2).
  - departments: departments or branches named, in English (e.g. "Computer Science", "Physics").
  - hostel_only: true if it is only for hostel residents.
  - lists_specific_students: true if it names particular students or roll numbers (a list or table of who must act).
  - conditions: other conditions in short English (e.g. "students with a backlog", "scholarship applicants"). Empty if none.
  - quote: the exact words from the notice that say who it is for, or null.
  Leave lists empty when the notice does not name them. Do not guess.
- items: what a student must do, and important dates.
  - kind: "action" for something the student must do (submit, pay, register, attend, collect); "event" for a date to know (exam starts, holiday, result).
  - what: a short English instruction, e.g. "Submit the exam form with the fee receipt at the department office".
  - date_text: the date or deadline exactly as written, or null. date_iso: YYYY-MM-DD, or null.
  - quote: the exact line in the notice this comes from.
  Include fees and amounts in "what". At most 14 items. Never invent dates, fees or steps that are not in the notice."""


def inline_schema(model: type[BaseModel]) -> dict:
    """Ollama's constrained decoding wants every field required (nullable ones can still be null) and no "$ref"s;
    optional fields let the small model skip them, and it will."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            out = {k: walk(v) for k, v in node.items()}
            if "properties" in out:
                out["required"] = list(out["properties"])
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


TRANSCRIBE = """Transcribe all the text on this notice page exactly as written, top to bottom, in its own language and script
(Hindi in Devanagari, English in English). Keep every date, number and name exactly. Write each table row on one line
with cells separated by " | ". Do not translate, summarise, explain or add anything."""


def build_messages(pages: list[Page]) -> list[dict]:
    text = "\n\n".join(f"--- page {p.number} ---\n{p.text}" for p in pages if p.text)[:MAX_TEXT_CHARS]
    return [{"role": "user", "content": PROMPT + "\n\nThe notice text:\n" + text}]


async def transcribe(page: Page) -> int:
    """Page image → page.text, in the notice's own script. Returns the model time."""
    reply = await ai.chat([{"role": "user", "content": TRANSCRIBE, "images": [base64.b64encode(page.jpeg).decode()]}],
                          num_predict=1500)
    text = reply.content.strip().strip("`").strip()
    if len(text) < 20:
        raise ai.AiUnavailable("Gemma couldn't make out any text on this page.")
    page.text = text
    return reply.latency_ms


async def read_notice(pages: list[Page]) -> tuple[RawNotice, int]:
    """Transcribe the image pages (in place), then pull the facts out of all the text."""
    ms = 0
    for p in pages:
        if p.jpeg and not p.text:
            ms += await transcribe(p)
    reply = await ai.chat(build_messages(pages), schema=inline_schema(RawNotice), num_predict=1800)
    try:
        return RawNotice.model_validate_json(reply.content), ms + reply.latency_ms
    except ValidationError as e:
        raise ai.AiUnavailable("The model's answer didn't validate.") from e


# --- checks (pure functions, unit-tested) -----------------------------------------------------

def _clean(s: str | None) -> str | None:
    s = " ".join((s or "").split())
    return s or None


def _key(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def tidy(raw: RawNotice, uploaded: date) -> dict:
    """Clean what the model returned, put real dates on every item, and drop repeats."""
    notice_date, _ = dates.resolve(raw.notice_date_text, raw.notice_date_iso, uploaded, last=False)
    if notice_date and abs((notice_date - uploaded).days) > 400:
        notice_date = None  # a misread year; relative deadlines fall back to the upload date
    ref = notice_date or uploaded
    a = raw.audience
    semesters = {s for s in a.semesters if 1 <= s <= 12}
    years = {y for y in a.years if 1 <= y <= 6}
    if semesters and years <= semesters:
        years = set()  # "3rd and 5th semester" came back as years [3, 5] too; the semesters are what was written
    audience = {
        "everyone": a.everyone,
        "programs": sorted({p for p in map(_clean, a.programs) if p}),
        "semesters": sorted(semesters),
        "years": sorted(years),
        "departments": sorted({d for d in map(_clean, a.departments) if d}),
        "hostel_only": a.hostel_only,
        "lists_specific_students": a.lists_specific_students,
        "conditions": [c for c in map(_clean, a.conditions) if c],
        "quote": _clean(a.quote),
    }
    items, seen = [], set()
    for it in raw.items:
        what = _clean(it.what)
        if not what or _key(what) in seen:
            continue
        seen.add(_key(what))
        when, note = dates.resolve(it.date_text, it.date_iso, ref, last=it.kind == "action")
        items.append({"kind": it.kind, "what": what, "due": when.isoformat() if when else None,
                      "date_text": _clean(it.date_text), "date_note": note, "quote": _clean(it.quote)})
    return {
        "title": _clean(raw.title) or "Untitled notice",
        "issued_by": _clean(raw.issued_by),
        "notice_date": notice_date.isoformat() if notice_date else None,
        "language": raw.language,
        "summary": _clean(raw.summary) or "",
        "audience": audience,
        "items": items,
    }
