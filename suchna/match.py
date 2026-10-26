"""Does this notice affect me? Plain code over what Gemma read, so every answer has a reason you can check.

Yes   — the notice names your course/semester/department (or all students), and nothing rules you out.
No    — it names a different course, semester, department, or only hostel residents.
Maybe — it is vague, has extra conditions, lists specific students we can't search, or your profile is missing a detail.
When unsure, say Maybe. A wrong "No" is the one mistake that costs a student a deadline.
"""

import math
import re

PROGRAMS = {
    "btech": {"btech", "be", "bachelor of technology", "bachelor of engineering", "बीटेक"},
    "mtech": {"mtech", "me", "master of technology", "master of engineering", "एमटेक"},
    "ba": {"ba", "bachelor of arts", "बीए"}, "ma": {"ma", "master of arts", "एमए"},
    "bsc": {"bsc", "bachelor of science", "बीएससी"}, "msc": {"msc", "master of science", "एमएससी"},
    "bcom": {"bcom", "bachelor of commerce", "बीकॉम"}, "mcom": {"mcom", "master of commerce", "एमकॉम"},
    "bba": {"bba"}, "mba": {"mba"}, "bca": {"bca"}, "mca": {"mca"},
    "llb": {"llb"}, "llm": {"llm"}, "bed": {"bed"}, "med": {"med"},
    "bpharm": {"bpharm"}, "mpharm": {"mpharm"}, "mbbs": {"mbbs"}, "diploma": {"diploma", "polytechnic"},
    "phd": {"phd", "research scholar", "research scholars", "doctoral", "शोध", "पीएचडी"},
    "ug": {"ug", "undergraduate", "undergraduates", "all ug", "स्नातक"},
    "pg": {"pg", "postgraduate", "postgraduates", "all pg", "स्नातकोत्तर"},
}
UG = {"btech", "ba", "bsc", "bcom", "bba", "bca", "llb", "bed", "bpharm", "mbbs", "diploma"}
PG = {"mtech", "ma", "msc", "mcom", "mba", "mca", "llm", "med", "mpharm"}

DEPARTMENTS = {
    "computer science": {"cse", "cs", "computer science", "computer engineering", "computer applications", "comp sci"},
    "information technology": {"it", "information technology"},
    "electronics": {"ece", "etc", "electronics", "electronics communication", "electronics and communication"},
    "electrical": {"ee", "eee", "electrical", "electrical electronics"},
    "mechanical": {"me", "mech", "mechanical"},
    "civil": {"ce", "civil"},
    "chemical": {"che", "chemical"},
    "ai": {"ai", "aiml", "ai ml", "artificial intelligence", "ai ds", "data science"},
}
_FILLER = r"\b(department|dept|of|and|engineering|engg|eng|branch|school|the|studies)\b"


def _flat(s: str) -> str:
    return re.sub(r"[^\w\s]|_", "", s.lower()).strip()


def program_key(name: str | None) -> str | None:
    if not name:
        return None
    flat, tight = _flat(name), re.sub(r"[\W_]+", "", name.lower())
    for key, names in PROGRAMS.items():
        if flat in names or tight in names:
            return key
    return None


def department_key(name: str | None) -> str | None:
    if not name:
        return None
    flat = _flat(name.replace("&", " and "))
    bare = " ".join(re.sub(_FILLER, " ", flat).split())
    for key, names in DEPARTMENTS.items():
        if flat in names or bare in names or bare == key:
            return key
    return bare or None


def year_of(semester: int | None) -> int | None:
    return math.ceil(semester / 2) if semester else None


def _same_words(a: str, b: str) -> bool:
    """"physics" matches "applied physics"; "it" does not match "civil"."""
    wa, wb = set(a.split()), set(b.split())
    return wa <= wb or wb <= wa


def _search_text(text: str, needle: str | None) -> bool:
    if not text or not needle or len(needle.strip()) < 3:
        return False
    return re.sub(r"\s+", "", needle.lower()) in re.sub(r"\s+", "", text.lower())


def verdict(audience: dict, profile: dict, *, text: str | None = None, override: str | None = None) -> dict:
    """→ {"answer": "yes"|"no"|"maybe", "reasons": [...]}. `text` is the notice's text layer, if any, for roll-number search."""
    if override in ("yes", "no"):
        return {"answer": override, "reasons": ["You marked this yourself."]}
    if not any(profile.get(k) for k in ("program", "semester", "department")):
        return {"answer": "maybe", "reasons": ["Add your course and semester in Profile, and I can tell you."]}

    yes, no, maybe = [], [], []
    roll, name = profile.get("roll_no"), profile.get("name")
    if text and (_search_text(text, roll) or (name and len(name) > 5 and _search_text(text, name))):
        return {"answer": "yes", "reasons": [f"Your {'roll number' if _search_text(text, roll) else 'name'} appears in this notice."]}
    if audience.get("lists_specific_students"):
        if text and roll:
            no.append(f"It lists specific students, and your roll number ({roll}) isn't in it.")
        else:
            maybe.append("It lists specific students. Check the list for your name or roll number.")

    specific = any(audience.get(k) for k in ("programs", "semesters", "years", "departments", "hostel_only"))
    if audience.get("everyone") and not specific:  # "all B.Tech students" is not "all students"
        yes.append("It's for all students.")

    progs = audience.get("programs") or []
    if progs:
        mine = program_key(profile.get("program"))
        keys = {program_key(p) for p in progs}
        level = "ug" if mine in UG else "pg" if mine in PG else None
        shown = ", ".join(progs)
        if not mine:
            maybe.append(f"It's for {shown}. Add your course in Profile to check.")
        elif mine in keys or (level and level in keys):
            yes.append(f"It's for {shown}, and you're {profile['program']}.")
        elif None in keys:
            maybe.append(f"It's for {shown}; I couldn't match that to {profile['program']}.")
        else:
            no.append(f"It's for {shown}, not {profile['program']}.")

    sems, years = audience.get("semesters") or [], audience.get("years") or []
    if sems or years:
        sem = profile.get("semester")
        parts = [f"semester {', '.join(map(str, sems))}"] if sems else []
        parts += [f"year {', '.join(map(str, years))}"] if years else []
        want = " or ".join(parts)
        if not sem:
            maybe.append(f"It's for {want}. Add your semester in Profile to check.")
        elif sem in sems or year_of(sem) in years:
            yes.append(f"It's for {want}, and you're in semester {sem}.")
        else:
            no.append(f"It's for {want}; you're in semester {sem} (year {year_of(sem)}).")

    depts = audience.get("departments") or []
    if depts:
        mine = department_key(profile.get("department"))
        keys = {department_key(d) for d in depts}
        shown = ", ".join(depts)
        known = set(DEPARTMENTS)
        if not mine:
            maybe.append(f"It's for {shown}. Add your department in Profile to check.")
        elif any(k and _same_words(k, mine) for k in keys):
            yes.append(f"It's for {shown}, your department.")
        elif mine in known and all(k in known for k in keys):
            no.append(f"It's for {shown}, not {profile['department']}.")
        else:
            maybe.append(f"It's for {shown}; I couldn't tell if that includes {profile['department']}.")

    if audience.get("hostel_only"):
        if profile.get("hostel") is False:
            no.append("It's only for hostel residents, and you're a day scholar.")
        elif profile.get("hostel") is None:
            maybe.append("It's only for hostel residents.")
        else:
            yes.append("It's for hostel residents, and you live in the hostel.")

    for c in audience.get("conditions") or []:
        maybe.append(f"Only if this is you: {c}.")

    if no:
        return {"answer": "no", "reasons": no}
    if maybe:
        return {"answer": "maybe", "reasons": maybe + yes}
    if yes:
        return {"answer": "yes", "reasons": yes}
    return {"answer": "maybe", "reasons": ["The notice doesn't say who it's for."]}
