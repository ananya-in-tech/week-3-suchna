import io
import json
import os
from datetime import date

os.environ["AI_WARMUP"] = "false"

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from suchna import ai, dates, extract, ics, main, match, reader
from suchna.db import DB

REF = date(2026, 10, 20)


# --- dates ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, want", [
    ("Last date: 25.10.2026", date(2026, 10, 25)),
    ("दिनांक 03/11/2026 तक", date(2026, 11, 3)),
    ("३०-१०-२०२६ तक जमा करें", date(2026, 10, 30)),
    ("by 5th November, 2026", date(2026, 11, 5)),
    ("25 अक्टूबर 2026", date(2026, 10, 25)),
    ("5 नवम्बर", date(2026, 11, 5)),
    ("November 7th", date(2026, 11, 7)),
    ("2026-12-01", date(2026, 12, 1)),
    ("within 7 days of this notice", date(2026, 10, 27)),
    ("सूचना जारी होने के 10 दिन के भीतर", date(2026, 10, 30)),
    ("10 January", date(2027, 1, 10)),  # no year, already past this year → next January
    ("25.10.26", date(2026, 10, 25)),
])
def test_find_dates(text, want):
    assert dates.find_dates(text, REF)[-1] == want


def test_ranges_and_fallback():
    assert dates.resolve("from 20.10.2026 to 25.10.2026", None, REF, last=True) == (date(2026, 10, 25), None)
    assert dates.resolve("from 20.10.2026 to 25.10.2026", None, REF, last=False) == (date(2026, 10, 20), None)
    # the model flipped day and month; the written date wins
    assert dates.resolve("03.11.2026", "2026-03-11", REF) == (date(2026, 11, 3), None)
    got, note = dates.resolve("next Monday", "2026-10-26", REF)
    assert got == date(2026, 10, 26) and "check" in note
    assert dates.resolve(None, None, REF) == (None, None)
    assert dates.find_dates("31.02.2026 and 99.99.9999", REF) == []


# --- legacy Hindi fonts -------------------------------------------------------------------------

KRUTI = ("fo'ofo|ky; }kjk lwfpr fd;k tkrk gS fd lHkh Nk=ksa dks ijh{kk QkWeZ fnukad 25-10-2026 rd "
         "tek djuk vfuok;Z gS rFkk foyEc 'kqYd ds lkFk")


def test_looks_legacy():
    assert extract.looks_legacy(KRUTI)
    assert extract.looks_legacy("Short text", ["BCDEEE+Kruti Dev 010"])
    assert not extract.looks_legacy("All students of B.Tech third semester must submit the examination form "
                                    "at the department office by 25.10.2026 along with the fee receipt.")
    assert not extract.looks_legacy("सभी छात्र-छात्राओं को सूचित किया जाता है कि परीक्षा फॉर्म दिनांक 25.10.2026 तक जमा करें। "
                                    "विलंब शुल्क के साथ फॉर्म 30.10.2026 तक स्वीकार किए जाएंगे।")


def test_garbled_hindi():
    assert extract.garbled_hindi("नमूना वə ȇ वə Ǿालय, डेमो नगर परʟZा नə यंŕक कायालय पŕांक: परʟZा/2026/418")
    assert not extract.garbled_hindi("नमूना विश्वविद्यालय, डेमो नगर। परीक्षा नियंत्रक कार्यालय। शुल्क ₹1500 है।")
    assert not extract.garbled_hindi("Café résumé naïve, all students must submit the form.")


def text_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    return doc.tobytes()


def test_pdf_paths():
    kind, pages, total = extract.read_file(text_pdf("Notice. All students of BA semester 3 must pay the fee by 25.10.2026. " * 3), "n.pdf")
    assert kind == "pdf" and total == 1 and pages[0].text and not pages[0].jpeg
    _, pages, _ = extract.read_file(text_pdf(KRUTI + " " + KRUTI), "n.pdf")
    assert pages[0].jpeg and not pages[0].text and "legacy" in pages[0].note
    _, pages, _ = extract.read_file(text_pdf(""), "scan.pdf")  # no text layer at all → scanned
    assert pages[0].jpeg and "scanned" in pages[0].note
    with pytest.raises(extract.BadFile):
        extract.read_file(b"not a file", "x.png")


def test_photo_loses_exif():
    img = Image.new("RGB", (2400, 1800), "white")
    exif = Image.Exif()
    exif.get_ifd(0x8825)[1] = "N"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    _, pages, _ = extract.read_file(buf.getvalue(), "photo.jpg")
    out = Image.open(io.BytesIO(pages[0].jpeg))
    assert max(out.size) == extract.MAX_SIDE and not out.getexif()


# --- does it affect me --------------------------------------------------------------------------

ME = {"name": "Ananya Kumari", "roll_no": "2301234", "program": "B.Tech", "department": "CSE", "semester": 3, "hostel": False}


def aud(**kw):
    base = {"everyone": False, "programs": [], "semesters": [], "years": [], "departments": [], "hostel_only": False,
            "lists_specific_students": False, "conditions": [], "quote": None}
    return base | kw


@pytest.mark.parametrize("audience, answer", [
    (aud(everyone=True), "yes"),
    (aud(programs=["B.Tech"], semesters=[3]), "yes"),
    (aud(programs=["BE"], years=[2]), "yes"),                      # BE = B.Tech; semester 3 is year 2
    (aud(programs=["UG"]), "yes"),
    (aud(programs=["M.Sc"]), "no"),
    (aud(programs=["B.Tech"], semesters=[5, 7]), "no"),
    (aud(departments=["Computer Science and Engineering"]), "yes"),
    (aud(departments=["Mechanical Engineering"]), "no"),
    (aud(departments=["School of Biosciences"]), "maybe"),          # unknown name: don't say no
    (aud(everyone=True, hostel_only=True), "no"),
    (aud(programs=["B.Tech"], semesters=[5], years=[3]), "no"),    # semester 3 is year 2
    (aud(everyone=True, conditions=["students with a backlog"]), "maybe"),
    (aud(), "maybe"),
    (aud(programs=["Shastri"]), "maybe"),
    (aud(lists_specific_students=True), "maybe"),
])
def test_verdict(audience, answer):
    assert match.verdict(audience, ME)["answer"] == answer


def test_verdict_roll_number_and_override():
    a = aud(lists_specific_students=True)
    assert match.verdict(a, ME, text="List: 2301230, 2301234, 2301240")["answer"] == "yes"
    assert match.verdict(a, ME, text="List: 2301230, 2301240")["answer"] == "no"
    assert match.verdict(aud(programs=["M.Sc"]), ME, override="yes")["answer"] == "yes"
    assert match.verdict(aud(everyone=True), {})["answer"] == "maybe"   # no profile yet
    hostel = match.verdict(aud(everyone=True, hostel_only=True), ME | {"hostel": True})
    assert hostel["answer"] == "yes" and hostel["reasons"] == ["It's for hostel residents, and you live in the hostel."]


def test_department_words():
    assert match.department_key("Dept. of Computer Science & Engg.") == "computer science"
    assert match.department_key("IT") == "information technology"
    assert not match._same_words("it", "civil")


# --- reader tidy --------------------------------------------------------------------------------

RAW = {
    "title": "  Exam form for odd semester ", "issued_by": "Controller of Examinations",
    "notice_date_text": "दिनांक 18.10.2026", "notice_date_iso": "2026-10-18", "language": "hindi",
    "summary": "Odd semester exam forms are open.",
    "audience": {"everyone": False, "programs": ["B.Tech", "B.Tech "], "semesters": [3, 5, 99], "years": [3, 5], "departments": [],
                 "hostel_only": False, "lists_specific_students": False, "conditions": [], "quote": "बी.टेक तृतीय एवं पंचम सेमेस्टर"},
    "items": [
        {"kind": "action", "what": "Submit the exam form", "date_text": "25.10.2026 तक", "date_iso": "2026-10-25", "quote": "फॉर्म 25.10.2026 तक जमा करें"},
        {"kind": "action", "what": "Submit the exam form.", "date_text": None, "date_iso": None, "quote": None},
        {"kind": "action", "what": "Pay late fee of Rs 500", "date_text": "सूचना के 10 दिन के भीतर", "date_iso": None, "quote": None},
        {"kind": "event", "what": "Exams start", "date_text": "from 10.11.2026 to 20.11.2026", "date_iso": None, "quote": None},
    ],
}


def test_tidy():
    t = reader.tidy(reader.RawNotice.model_validate(RAW), REF)
    assert t["title"] == "Exam form for odd semester" and t["notice_date"] == "2026-10-18"
    assert t["audience"]["programs"] == ["B.Tech"] and t["audience"]["semesters"] == [3, 5]
    assert t["audience"]["years"] == []   # copied from the semesters
    assert [i["what"] for i in t["items"]] == ["Submit the exam form", "Pay late fee of Rs 500", "Exams start"]
    assert t["items"][1]["due"] == "2026-10-28"   # 10 days from the notice date, not the upload date
    assert t["items"][2]["due"] == "2026-11-10"   # an event takes the first day of the range


def test_schema_is_ollama_ready():
    s = reader.inline_schema(reader.RawNotice)
    assert "$defs" not in json.dumps(s)
    assert set(s["required"]) == set(s["properties"])
    assert set(s["properties"]["audience"]["required"]) == set(s["properties"]["audience"]["properties"])


def test_ics():
    out = ics.calendar([{"uid": "item-1", "due": "2026-10-25", "summary": "Due: Submit form, with fee; now",
                         "description": "x" * 200}])
    assert "DTSTART;VALUE=DATE:20261025" in out and "Submit form\\, with fee\\; now" in out
    assert all(len(line.encode()) <= 75 for line in out.split("\r\n"))


# --- API ----------------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    from suchna.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    main.set_db(DB(tmp_path / "test.db"))
    with TestClient(main.app) as c:
        yield c


def test_flow(client, monkeypatch):
    async def fake_chat(messages, **kw):
        assert "The notice text" in messages[0]["content"] and "images" not in messages[0]
        return ai.Reply(json.dumps(RAW, ensure_ascii=False), 1234)

    monkeypatch.setattr(ai, "chat", fake_chat)
    monkeypatch.setattr(main, "today", lambda: REF)
    client.put("/api/profile", json={"program": "B.Tech", "semester": 3, "department": "CSE", "hostel": False})
    pdf = text_pdf("Notice. All students of B.Tech semester 3 must submit the exam form by 25.10.2026. " * 3)
    r = client.post("/api/notices", files=[("files", ("exam.pdf", pdf, "application/pdf"))])
    assert r.status_code == 201
    nid = r.json()["ids"][0]

    n = client.get(f"/api/notices/{nid}").json()
    for _ in range(50):
        if n["status"] == "done":
            break
        import time; time.sleep(0.1)
        n = client.get(f"/api/notices/{nid}").json()
    assert n["status"] == "done", n
    assert n["verdict"]["answer"] == "yes" and n["next"]["what"] == "Submit the exam form"
    assert client.get(f"/api/notices/{nid}/preview.jpg").status_code == 200

    item = n["items"][0]["id"]
    assert client.patch(f"/api/items/{item}", json={"done": True}).json()["done"] == 1
    cal = client.get("/api/calendar.ics").text
    assert "Pay late fee" in cal and "Submit the exam form" not in cal   # done items leave the calendar

    client.put("/api/profile", json={"program": "M.Sc", "semester": 1})
    assert client.get(f"/api/notices/{nid}").json()["verdict"]["answer"] == "no"
    assert client.patch(f"/api/notices/{nid}", json={"override": "yes"}).json()["verdict"]["answer"] == "yes"
    assert client.delete(f"/api/notices/{nid}").status_code == 204
    assert client.get("/api/notices").json()["notices"] == []


def test_photo_is_transcribed_first(client, monkeypatch):
    calls = []

    async def fake_chat(messages, **kw):
        calls.append(kw.get("schema") is not None)
        if "images" in messages[0]:
            return ai.Reply("नमूना विश्वविद्यालय\nबी.टेक तृतीय सेमेस्टर के छात्र 25.10.2026 तक फॉर्म जमा करें।", 900)
        assert "बी.टेक तृतीय" in messages[0]["content"]   # the facts step reads the transcription
        return ai.Reply(json.dumps(RAW, ensure_ascii=False), 1100)

    monkeypatch.setattr(ai, "chat", fake_chat)
    buf = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(buf, "JPEG")
    nid = client.post("/api/notices", files=[("files", ("board.jpg", buf.getvalue(), "image/jpeg"))]).json()["ids"][0]
    import time
    for _ in range(50):
        n = client.get(f"/api/notices/{nid}").json()
        if n["status"] == "done":
            break
        time.sleep(0.1)
    assert calls == [False, True] and n["latency_ms"] == 2000 and "बी.टेक" in n["text"]


def test_upload_rejects_junk(client):
    r = client.post("/api/notices", files=[("files", ("notes.txt", b"hello", "text/plain"))])
    assert r.status_code == 400


# --- hosted demo --------------------------------------------------------------------------------

def test_demo_mode(tmp_path, monkeypatch):
    from suchna.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)
    monkeypatch.setattr(s, "demo", True)
    monkeypatch.setattr(s, "ai_enabled", False)
    monkeypatch.setattr(main, "today", lambda: date(2026, 11, 2))   # a week after the export
    main.set_db(DB(tmp_path / "demo.db"))
    with TestClient(main.app) as c:
        h = c.get("/api/health").json()
        assert h["demo"]["shift_days"] == 7
        ns = c.get("/api/notices").json()["notices"]
        names = {n["original_name"] for n in ns}
        assert names == {"hindi_holiday_photo.jpg", "english_hostel_fee.pdf", "hindi_exam_form.pdf", "bilingual_scholarship_scan.pdf"}
        exam = next(n for n in ns if n["original_name"] == "hindi_exam_form.pdf")
        assert exam["verdict"]["answer"] == "yes"                     # default demo profile: B.Tech sem 3
        assert exam["items"][0]["due"] == "2026-11-04"                # 28 Oct moved a week forward
        assert c.get(f"/api/notices/{exam['id']}/preview.jpg").status_code == 200

        # each visitor's profile is their own cookie, never the shared database
        r = c.put("/api/profile", json={"program": "BA", "semester": 1})
        assert "suchna_profile" in r.cookies
        assert next(n for n in c.get("/api/notices").json()["notices"] if n["id"] == exam["id"])["verdict"]["answer"] == "no"
        assert main.db().profile()["program"] is None
        c.cookies.clear()
        assert c.get("/api/profile").json()["program"] == "B.Tech"

        assert c.post("/api/notices", files=[("files", ("x.pdf", b"%PDF-1.4", "application/pdf"))]).status_code == 403
        assert c.patch(f"/api/items/{exam['items'][0]['id']}", json={"done": True}).status_code == 403
        assert c.delete(f"/api/notices/{exam['id']}").status_code == 403
