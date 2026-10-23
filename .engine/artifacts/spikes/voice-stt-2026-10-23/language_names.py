"""Endonyms for the language list of task 106 from CLDR (Babel); codes CLDR lacks or misnames are set by hand.

Run: `uv run --no-project --with babel python language_names.py "<codes>"`. Babel is not a dependency of the
project, so it is loaded by name (the module is typed as Any).
"""

import collections
import importlib
import sys
import unicodedata

Locale = importlib.import_module("babel").Locale
HAND = {"rup-BG": "Armãneashti", "ka-GE": "ქართული", "cmn-Hans-CN": "中文 (简体)"}


def base(code: str) -> str:
    return code.split("-")[0]


def cap(name: str) -> str:
    return name[:1].upper() + name[1:]


def key(name: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)).casefold()


def row(code: str, count: collections.Counter[str]) -> tuple[str, str, str]:
    if code in HAND:
        return code, HAND[code], "hand"
    lang = base(code)
    loc = Locale.parse(lang)
    name = cap(str(loc.get_display_name(loc)))
    if count[lang] > 1:
        parts = code.split("-")[1:]
        extra = loc.scripts["Guru"] if "Guru" in parts else loc.territories[parts[-1]]
        name = f"{name} ({extra})"
    if code == "sd-Arab-IN":
        name = f"{name} ({loc.territories['IN']})"
    return code, name, "CLDR"


def main(codes: list[str]) -> None:
    count = collections.Counter(base(c) for c in codes)
    rows = [row(code, count) for code in codes]
    names = [r[1] for r in rows]
    dup = [n for n, k in collections.Counter(names).items() if k > 1]
    for r in sorted(rows, key=lambda r: key(r[1])):
        print("\t".join(r))
    print("DUPLICATES", dup, "N", len(rows), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1].split())
