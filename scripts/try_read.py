"""Read notices with Gemma from the command line and print what came out, with timings.

    .venv/Scripts/python scripts/try_read.py samples/*.pdf samples/*.jpg
"""

import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suchna import extract, match, reader  # noqa: E402

ME = {"program": "B.Tech", "department": "CSE", "semester": 3, "hostel": True}


async def main(paths: list[str]) -> None:
    for path in paths:
        raw = Path(path).read_bytes()
        kind, pages, total = extract.read_file(raw, path)
        started = time.perf_counter()
        notice, ms = await reader.read_notice(pages)
        facts = reader.tidy(notice, date.today())
        v = match.verdict(facts["audience"], ME, text="\n".join(p.text for p in pages if p.text) or None)
        print(f"\n=== {path} ({kind}, {[p.note for p in pages]}) model {ms / 1000:.0f}s, total {time.perf_counter() - started:.0f}s")
        print(json.dumps(facts, ensure_ascii=False, indent=1))
        print("VERDICT for", ME, "→", v)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
