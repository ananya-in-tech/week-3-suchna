"""Export the local readings of the SAMPLE notices into demo/ for the hosted demo (see suchna/demo.py).

    .venv/Scripts/python scripts/make_samples.py   # if samples/ is empty
    # drop the samples into the local app and let Gemma read them, then:
    .venv/Scripts/python scripts/export_demo.py

Only files whose names match samples/ are exported, so your own notices never end up in the demo.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from suchna import demo  # noqa: E402
from suchna.config import get_settings  # noqa: E402
from suchna.db import DB  # noqa: E402

if __name__ == "__main__":
    s = get_settings()
    names = {p.name for p in (ROOT / "samples").iterdir() if p.is_file()}
    count = demo.export(DB(s.db_path), names, s.data_dir / "notices", date.today())
    print(f"exported {count} sample readings to {demo.SEED.relative_to(ROOT)}")
