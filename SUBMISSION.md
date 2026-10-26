---
title: "Suchna: I stopped reading university notices. A local Gemma reads the Hindi ones for me"
published: false
tags: devchallenge, hf26challenge, ai, opensource
cover_image: https://raw.githubusercontent.com/ananya-in-tech/week-3-suchna/main/imgs/cover.png
---

*This is a submission for the [Hacktoberfest 2026 Open-Source AI Challenge, Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).*

<!-- ✍️ cover_image points at imgs/cover.png in the GitHub repo: check the repo name after pushing, or upload the file in DEV's editor. -->
<!-- ✍️ Placeholders marked ✍️ need real details. Don't present the SAMPLE notices as real usage. -->

## What I Built

✍️ *Open with the real moment: the WhatsApp group, the 14th PDF of the week, the deadline you nearly missed.*

University notices reach students as PDFs forwarded on WhatsApp and photos of the notice board. Many are in Hindi,
the date is buried in the third paragraph, and most of them aren't for you. But the one that is has a deadline.

**Suchna** (सूचना, "notice") reads them for you. Drop a PDF or a photo and walk away. A few minutes later it has
answered three questions in plain English:

1. **Does this affect me?** Yes / Maybe / No, with the reason and the notice's own Hindi line as proof.
2. **What do I need to do?** A checklist.
3. **By when?** Real dates and "in 3 days", in one "Next up" list across all notices, and in your calendar.

It fits the theme because the laziest way to deal with a notice is to never read it, and still not miss the deadline.

## Demo

[Hosted Demo link](https://suchna.onrender.com/)

## Code

{% github ananya-in-tech/week-3-suchna %} <!-- ✍️ check the repo name -->

## How I Built It

- **FastAPI + vanilla JS + SQLite + PyMuPDF**, about 1,700 lines, running on my laptop (i5-1240P, no GPU).
- **Two steps for images:** Gemma first only transcribes the page in its own script, then extracts facts from that text.
- **Gemma 4 E2B** through **Ollama**, with a JSON schema (constrained decoding), so every answer has the same shape:
  who the notice is for, the actions, the dates, and the original quote for each.
- **Gemma reads, code decides.** The model never sees my profile. "Does this affect me?" is ~150 lines of plain
  Python that compares the notice's audience (course, semester/year, department, hostel, roll-number lists) with my profile.
  That makes every answer explainable, testable, and instant to redo when I change semester.
- **Dates are parsed in code**: `25.10.2026`, `२५ अक्टूबर`, `5th Nov`, `from 20.10 to 25.10`, and `within 10 days of
  this notice` (counted from the notice's own date). Indian dates are day-first, and small models sometimes flip
  `03.11` into March. So the written date wins, and the model's guess is only a flagged fallback.
- **When unsure, say Maybe.** A wrong "No" is the one mistake that costs a deadline.

### Hindi PDFs lie

The most interesting bug: a Hindi PDF that *looks* perfect gives garbage when you extract its text.

- **Legacy fonts.** Kruti Dev and DevLys map Hindi glyphs onto ASCII, so "विश्वविद्यालय द्वारा" comes out as
  `fo'ofo|ky; }kjk`. Suchna spots these by font name and by the shape of the text.
- **Broken Unicode.** Even in a Unicode Hindi PDF, conjuncts can map to the wrong characters:
  my own generated sample came out as `वə ȇ वə Ǿालय` for "विश्वविद्यालय".

Both kinds of page are rendered to an image and read by Gemma's vision instead. ✍️ *Did this happen with your real notices?*

### Numbers

On my laptop (i5-1240P, no GPU), Gemma 4 E2B takes about **45 s for a text PDF** and **2.5–3 minutes for a
scanned page or photo**. That's slow, and it's fine: you drop the notice and walk away. The theme literally says "slow and steady".

On my four generated test notices (Hindi PDF, English PDF, Hindi photo, scanned bilingual PDF), all four verdicts
were right, and 8 of 9 deadlines came out on the right date. ✍️ *Replace with numbers from real notices.*

### What went wrong

- **Reading a photo in one go.** Gemma quoted the Hindi word-perfect, then invented the title: a Diwali holiday
  notice became "examination schedule". Splitting it into two steps (*transcribe the page*, then *extract facts
  from the text*) fixed it, and was faster.
- **A wrong "No" for a hostel resident.** "Hostel fee for the even semester" was read as "only for semester 2".
  The prompt now separates the semester a notice is *about* from the students who must *act*.
- **A worker that died quietly.** My background queue's `asyncio.Event` was created at import time, bound to the
  first event loop, so the worker crashed on the next start. A test caught it.

## Why Does Open Innovation Matter?

- **Privacy.** My profile has my roll number and course. Notices list students by name, roll number and
  sometimes fee dues. None of it leaves the laptop: Suchna refuses to start if the model host isn't local.
- **Zero ongoing cost.** A student reading 20 notices a week shouldn't need an API key or a subscription.
- **Works on bad Wi-Fi.** Hostel internet is unreliable; a local model is not.
- **Swappable.** The model is one env var. If a better open Hindi model comes out, I change `OLLAMA_MODEL`.
- **Transparent.** The decision logic is code you can read, not a hidden prompt.

## The Lazy Payoff

✍️ *How much reading did it save you this week? "Of 12 notices, 3 were mine; I read none of them in full."*

## Prize Categories

<!-- ✍️ Render hosts the read-only demo (front end + API, no AI). Check the Best Use of Render rules before claiming it:
     they name Render "as the AI runtime" or "to host an agent's front end", and the AI here runs locally. -->
**Render**: the public demo runs on Render's free plan. Gemma itself runs on the student's own laptop, by design.

<!-- Optional: embed a DevRelay session recording of the build. -->
