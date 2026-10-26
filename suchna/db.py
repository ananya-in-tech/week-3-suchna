"""SQLite store on this computer: your profile, the notices you dropped in, and what each one asks of you."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    data  TEXT NOT NULL              -- JSON: name, roll_no, university, program, department, semester, hostel
);
CREATE TABLE IF NOT EXISTS notices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file          TEXT NOT NULL,     -- stored copy in data/notices/
    original_name TEXT NOT NULL,
    kind          TEXT NOT NULL,     -- pdf | image
    status        TEXT NOT NULL,     -- queued | reading | done | failed
    error         TEXT,
    pages_read    INTEGER,
    pages_total   INTEGER,
    page_notes    TEXT,              -- JSON list: how each page was read (text layer / vision and why)
    text          TEXT,              -- the PDF's text layer, when usable (for roll-number search)
    title         TEXT,
    issued_by     TEXT,
    notice_date   TEXT,              -- YYYY-MM-DD
    language      TEXT,
    summary       TEXT,
    audience      TEXT,              -- JSON from reader.tidy
    override      TEXT,              -- yes | no | NULL (you said so)
    latency_ms    INTEGER,
    created_at    TEXT NOT NULL,
    read_at       TEXT
);
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id  INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,        -- action | event
    what       TEXT NOT NULL,
    due        TEXT,                 -- YYYY-MM-DD
    date_text  TEXT,                 -- as written in the notice
    date_note  TEXT,                 -- why to double-check the date (NULL = parsed from the notice)
    quote      TEXT,
    done       INTEGER NOT NULL DEFAULT 0,
    done_at    TEXT
);
CREATE TABLE IF NOT EXISTS ai_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, latency_ms INTEGER NOT NULL, ok INTEGER NOT NULL,
    pages INTEGER, vision INTEGER
);
"""

PROFILE_KEYS = ("name", "roll_no", "university", "program", "department", "semester", "hostel")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.conn() as c:
            c.executescript(SCHEMA)
            c.execute("UPDATE notices SET status = 'queued' WHERE status = 'reading'")  # interrupted last run

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # --- profile ---

    def profile(self) -> dict:
        with self.conn() as c:
            row = c.execute("SELECT data FROM profile WHERE id = 1").fetchone()
        data = json.loads(row["data"]) if row else {}
        return {k: data.get(k) for k in PROFILE_KEYS}

    def save_profile(self, data: dict) -> dict:
        clean = {k: data.get(k) for k in PROFILE_KEYS}
        with self.conn() as c:
            c.execute("INSERT INTO profile (id, data) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                      (json.dumps(clean, ensure_ascii=False),))
        return clean

    # --- notices ---

    def add_notice(self, file: str, original_name: str, kind: str) -> int:
        with self.conn() as c:
            return c.execute("INSERT INTO notices (file, original_name, kind, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
                             (file, original_name, kind, now_iso())).lastrowid

    @staticmethod
    def _notice(row) -> dict:
        n = dict(row)
        n["audience"] = json.loads(n["audience"]) if n["audience"] else None
        n["page_notes"] = json.loads(n["page_notes"]) if n["page_notes"] else []
        return n

    def notice(self, nid: int) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM notices WHERE id = ?", (nid,)).fetchone()
        return self._notice(row) if row else None

    def notices(self) -> list[dict]:
        with self.conn() as c:
            rows = c.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
        return [self._notice(r) for r in rows]

    def next_queued(self) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM notices WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
        return self._notice(row) if row else None

    def set_status(self, nid: int, status: str, error: str | None = None) -> None:
        with self.conn() as c:
            c.execute("UPDATE notices SET status = ?, error = ? WHERE id = ?", (status, error, nid))

    def save_reading(self, nid: int, facts: dict, *, text: str | None, page_notes: list[str], pages_read: int,
                     pages_total: int, latency_ms: int) -> None:
        """Replace whatever was read before (a re-read keeps the done ticks of items that come back the same)."""
        with self.conn() as c:
            done = {r["what"].lower(): r["done_at"] for r in
                    c.execute("SELECT what, done_at FROM items WHERE notice_id = ? AND done = 1", (nid,))}
            c.execute("DELETE FROM items WHERE notice_id = ?", (nid,))
            c.execute("""UPDATE notices SET status = 'done', error = NULL, title = ?, issued_by = ?, notice_date = ?,
                         language = ?, summary = ?, audience = ?, text = ?, page_notes = ?, pages_read = ?,
                         pages_total = ?, latency_ms = ?, read_at = ? WHERE id = ?""",
                      (facts["title"], facts["issued_by"], facts["notice_date"], facts["language"], facts["summary"],
                       json.dumps(facts["audience"], ensure_ascii=False), text, json.dumps(page_notes), pages_read,
                       pages_total, latency_ms, now_iso(), nid))
            for it in facts["items"]:
                was = done.get(it["what"].lower())
                c.execute("""INSERT INTO items (notice_id, kind, what, due, date_text, date_note, quote, done, done_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (nid, it["kind"], it["what"], it["due"], it["date_text"], it["date_note"], it["quote"],
                           int(was is not None), was))

    def set_override(self, nid: int, override: str | None) -> None:
        with self.conn() as c:
            c.execute("UPDATE notices SET override = ? WHERE id = ?", (override, nid))

    def requeue(self, nid: int) -> None:
        self.set_status(nid, "queued")

    def delete_notice(self, nid: int) -> dict | None:
        n = self.notice(nid)
        if n:
            with self.conn() as c:
                c.execute("DELETE FROM notices WHERE id = ?", (nid,))
        return n

    # --- items ---

    def items(self, nid: int | None = None) -> list[dict]:
        with self.conn() as c:
            if nid is None:
                rows = c.execute("SELECT * FROM items ORDER BY due IS NULL, due, id").fetchall()
            else:
                rows = c.execute("SELECT * FROM items WHERE notice_id = ? ORDER BY kind, due IS NULL, due, id", (nid,)).fetchall()
        return [dict(r) for r in rows]

    def item(self, iid: int) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM items WHERE id = ?", (iid,)).fetchone()
        return dict(row) if row else None

    def set_done(self, iid: int, done: bool) -> None:
        with self.conn() as c:
            c.execute("UPDATE items SET done = ?, done_at = ? WHERE id = ?", (int(done), now_iso() if done else None, iid))

    def log_ai(self, latency_ms: int, ok: bool, pages: int, vision: int) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO ai_calls (at, latency_ms, ok, pages, vision) VALUES (?, ?, ?, ?, ?)",
                      (now_iso(), latency_ms, int(ok), pages, vision))
