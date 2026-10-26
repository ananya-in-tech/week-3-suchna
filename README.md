# Suchna (सूचना): university notices, read for you

**Hacktoberfest 2026 · DEV Open-Source AI Challenge · Week 3: Slow and Steady**

| | |
|---|---|
| Challenge | https://dev.to/challenges/hacktoberfest-week3-2026-10-19 |
| Dates | Oct 19 – Oct 25, 2026 (built Oct 26, after the deadline) |
| Theme | Build something with open-weight models that rewards laziness: relax, automate a dreaded task, make life easier |
| Tags | `devchallenge`, `hf26challenge` |
| Status | Built · tested on SAMPLE notices · waiting for real notices · post draft in [SUBMISSION.md](SUBMISSION.md) |

University notices arrive as PDFs on WhatsApp groups and photos of the notice board. Half are in Hindi, the date is
buried in the third paragraph, and most of them aren't for you. Suchna reads them so you don't have to:

> **Does this affect me? What do I need to do, and by when?** In plain English, with the original Hindi line as proof.

Drop a PDF or a photo and walk away. Gemma 4 reads it on your own laptop, and Suchna puts every deadline that's
yours into one list (and your calendar).

## What it does

- **Reads Hindi, English or both**, from text PDFs, scanned PDFs and phone photos. Answers are always in English.
- **"Does this affect me?"**: Yes / Maybe / No against your course, semester, department, hostel and roll number,
  with the reason ("It's for B.Tech semester 3, 5, and you're in semester 3") and the notice's own words.
- **What to do, by when**: a checklist of actions with real dates and "in 3 days", plus "dates to know" (exams, holidays).
- **Next up**: every open deadline across all your notices, soonest first. **Add to calendar** exports an `.ics` file
  with a reminder the evening before.
- **Lazy inbox**: save notice files into `data/inbox/` (for example from WhatsApp Desktop) and Suchna picks them up
  by itself, one at a time, in the background.
- **You can overrule it**: "It's for me" / "Not for me" on any notice.

## How it works

```
PDF / photo ──► extract.py ──┬─ good text layer ───────────► text ─┐
                             ├─ legacy Hindi font (Kruti Dev) ─► page image ─┤
                             ├─ garbled Unicode Hindi ─────► page image ─┤──► Gemma 4 E2B (Ollama, local)
                             └─ scanned page / photo ──────► page image ─┘        │ 1. images: transcribe only
                                                                                  │ 2. text → JSON schema: who it's
                                                                                  │    for, actions, dates, quotes
                         dates.py: "25.10.2026", "२५ अक्टूबर", "within 7 days" ◄──┘
                                       │ real dates in code, day-first
                         match.py: your profile × "who it's for" → Yes / Maybe / No + reasons
                                       │ plain code, no model call
                                  SQLite inbox · checklist · .ics
```

- **Gemma reads, code decides.** The model returns facts in a fixed JSON schema (Ollama constrained decoding).
  It never sees your profile. Whether a notice affects you is plain, unit-tested code in [match.py](suchna/match.py),
  so every answer has a reason you can check, and editing your profile re-sorts every notice instantly.
- **Dates are parsed in code** ([dates.py](suchna/dates.py)): day-first numeric dates, Hindi month names,
  Devanagari digits, ranges, missing years and "within 10 days of this notice". The model's own date is only a
  fallback, and it's flagged "please check".
- **When unsure, say Maybe.** A wrong "No" is the mistake that costs a student a deadline.
- **Hindi PDFs lie.** Two kinds of broken text layer are detected and sent to vision instead: legacy fonts
  (Kruti Dev text comes out as `fo'ofo|ky;`) and Unicode Hindi with a bad character map (`वə ȇ वə Ǿालय`).

## Run it

Needs [Ollama](https://ollama.com) and Python 3.12+.

```powershell
ollama pull gemma4:e2b
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.\scripts\dev.ps1            # http://localhost:8030
```

Then open **Profile**, add your course and semester, and drop a notice.

- `scripts/make_samples.py` makes four SAMPLE notices in `samples/` (Hindi PDF, English PDF, Hindi photo, scanned bilingual PDF).
  They are generated test files, not real notices.
- `scripts/try_read.py samples/*` reads notices from the command line and prints what Gemma returned, with timings.
- `scripts/make_cover.py` draws the DEV cover, [imgs/cover.png](imgs/cover.png).
- `.venv\Scripts\python -m pytest` runs the tests (dates, matching, font detection, API flow with a fake model).

## Hosted demo (Render, free)

Gemma needs several GB of RAM and Render's free plan has 512 MB, so the hosted Suchna is a **read-only demo**
(`DEMO=true`, AI off). It shows Gemma's real readings of the four SAMPLE notices from [demo/seed.json](demo/seed.json).
Visitors can change the profile (kept in their own browser cookie, never on the server) and watch the answers
change. Uploading, ticking and deleting are off. Dates are moved forward by the days since the export, so the
deadlines stay ahead, and the page says so.

Deploy:

1. Push this folder to its own GitHub repo (e.g. `week-3-suchna`). `render.yaml` must be at the repo root.
2. On [render.com](https://render.com): **New → Blueprint**, pick the repo, **Apply**. It builds with Python 3.12 on the free plan.
3. Open the `.onrender.com` URL. The first visit after 15 idle minutes takes ~1 minute while the free server wakes up.
4. If the repo isn't `ananya-in-tech/week-3-suchna`, set `REPO_URL` in the Render environment so the demo links to it.

To refresh the demo readings: read the files in `samples/` locally, then run `scripts/export_demo.py`
(it exports only files named like the samples, never your own notices).

## Privacy

Your profile, notices and deadlines live in `data/` on your computer (git-ignored). Suchna refuses to start if
`OLLAMA_HOST` isn't local or the model is a `:cloud` tag, unless you set `ALLOW_REMOTE_AI=true` on purpose.
Photos are re-encoded on upload, so EXIF and location data are dropped.

## Results

So far only on the four generated **SAMPLE** notices in `samples/` (not real notices), on an i5-1240P laptop with no GPU,
for a B.Tech CSE semester-3 hostel profile:

| Sample | Path | Model time | Verdict | Dates |
|---|---|---|---|---|
| English hostel fee (text PDF) | text layer | 43 s | Yes (hostel residents) ✔ | 3 of 3 ✔ |
| Hindi exam form (Unicode PDF, garbled text layer) | vision, 2 steps | 150 s | Yes (B.Tech sem 3, 5) ✔ | 3 of 4 ✔, late-fee date missed |
| Hindi holiday (phone-style photo) | vision, 2 steps | 179 s | Yes (all students) ✔ | 2 of 2 ✔ |
| Bilingual scholarship (scanned PDF) | vision, 2 steps | 168 s | No (BA/B.Sc/B.Com only) ✔ | table dates merged into one |

What changed along the way:

- **One step from a photo didn't work.** Asked to read a photo and extract facts in one call, Gemma quoted the Hindi
  word-perfect but invented the title ("exam schedule" for a Diwali holiday) and the audience. Two steps
  (transcribe first, then extract from text) fixed it and were *faster* (150–180 s instead of 186–248 s).
- **"Fee for the even semester" is not "for semester 2 students".** That first gave a hostel resident a wrong **No**.
  The prompt now separates the semester a notice is *about* from the students who must *act*.
- Gemma copied semesters into years ("3rd and 5th semester" → years 3, 5); code drops those.

<!-- ✍️ Add real notices here: how many, Hindi/English/scan, seconds each, verdicts right/wrong. -->

## License

MIT, see [LICENSE](LICENSE).
