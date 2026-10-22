"""Helpers for the skel-guards-deploy contract tests (slice tester). Built from the contract, not the code.

- ROOT, read_or_fail: the repository root; a file the slice must create is read, or the test fails on an
  assertion (not on an error) while it is missing.
- dockerfile_instructions: the Dockerfile as (INSTRUCTION, arguments) pairs — comments dropped, `\\`
  continuations joined.
- ignored: whether a path is matched by a non-negated `.dockerignore` pattern (Docker's rules: `*` and `?`
  stay inside one path segment, `**` crosses them, a pattern matching a directory matches all under it).
- commands: every occurrence of a command phrase in `docs/deploy.md`, with its text — the rest of the line
  from the phrase on, plus every following line while the previous one ends in `\\`.
- run_pytest: one pytest run of the given ids in a subprocess, from the root, with this interpreter.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]


def read_or_fail(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"{rel} does not exist"
    return path.read_text(encoding="utf-8")


def dockerfile_instructions() -> list[tuple[str, str]]:
    text = read_or_fail("Dockerfile")
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if buf and line.startswith("#"):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        logical.append(buf)
        buf = ""
    if buf.strip():
        logical.append(buf)
    out = []
    for line in logical:
        word, _, rest = line.partition(" ")
        out.append((word.upper(), rest.strip()))
    return out


def env_values(instructions: list[tuple[str, str]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for word, args in instructions:
        if word != "ENV":
            continue
        if "=" in args.split()[0]:
            for item in re.findall(r'(\w+)=("[^"]*"|\S+)', args):
                values[item[0]] = item[1].strip('"')
        else:
            key, _, value = args.partition(" ")
            values[key] = value.strip().strip('"')
    return values


def without_flags(args: str) -> list[str]:
    return [part for part in args.split() if not part.startswith("--")]


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def dockerignore_patterns() -> list[str]:
    text = read_or_fail(".dockerignore")
    patterns = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line.lstrip("/").rstrip("/").removeprefix("./"))
    return patterns


def ignored(path: str) -> bool:
    parts = path.split("/")
    prefixes = ["/".join(parts[: n + 1]) for n in range(len(parts))]
    return any(_pattern_regex(p).match(prefix) for p in dockerignore_patterns() for prefix in prefixes)


@dataclass(frozen=True)
class Command:
    line: int  # 1-based line of the doc where the phrase occurs
    text: str


def commands(doc: str, phrase: str) -> list[Command]:
    lines = doc.splitlines()
    found = []
    for i, line in enumerate(lines):
        at = line.find(phrase)
        if at < 0:
            continue
        text = line[at:]
        j = i
        while lines[j].rstrip().endswith("\\") and j + 1 < len(lines):
            j += 1
            text += "\n" + lines[j]
        found.append(Command(i + 1, text))
    return found


def run_pytest(*ids: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *ids],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def guards_module() -> ModuleType:
    path = ROOT / "tests" / "test_a3_guards.py"
    assert path.is_file(), "tests/test_a3_guards.py does not exist"
    spec = importlib.util.spec_from_file_location("skelgd_a3_guards_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
