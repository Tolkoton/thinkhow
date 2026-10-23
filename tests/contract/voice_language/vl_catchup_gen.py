"""Helper for the voice-language catch-up tests of `language_names.py` (slice tester), from the contract.

The contract («Seam», `LANGUAGES`): the names come from `languages.tsv`, «зроблений `language_names.py`: CLDR
через Babel». Babel is not a dependency of the application (the same line), so the generator is run the way it
is run by hand: `uv run --offline --no-project --with babel python language_names.py "<codes>"` — an
ephemeral environment from uv's cache; nothing is added to the project. When uv or a cached Babel is not
there, the tests that need the generator are skipped, with the reason.

The generator's interface (its public surface, not its body): the codes as one space-separated argument;
one line per language on stdout, `code<TAB>name<TAB>...`.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SPIKE = REPO / ".engine/artifacts/spikes/voice-stt-2026-10-23"
GENERATOR = SPIKE / "language_names.py"
TSV = SPIKE / "languages.tsv"
GOOGLE_TABLE = SPIKE / "google_language_table.txt"


def _uv(*args: str) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    if uv is None:
        # gate-allow: generator needs uv (Babel is no project dependency)
        pytest.skip("uv is not on PATH: the generator needs Babel from uv's cache")
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(
            [uv, "run", "--offline", "--no-project", "--with", "babel", "python", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )


@functools.cache
def _babel_ready() -> str:
    probe = _uv("-c", "import babel")
    return "" if probe.returncode == 0 else probe.stderr[-500:]


@functools.cache
def generate(codes: str) -> str:
    """stdout of the generator for one space-separated string of codes."""
    problem = _babel_ready()
    if problem:
        # gate-allow: Babel absent offline, generator cannot run
        pytest.skip(f"Babel is not available offline through uv: {problem}")
    done = _uv(str(GENERATOR), codes)
    assert done.returncode == 0, done.stderr
    return done.stdout


def pairs(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        code, name = line.split("\t")[:2]
        rows.append((code, name))
    return rows


def model_codes_without_ru() -> list[str]:
    """The model's codes in its order, without `ru-RU` (rows `code | name | status`, `#` skipped)."""
    codes: list[str] = []
    for line in GOOGLE_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        code = line.split("|")[0].strip()
        if code != "ru-RU":
            codes.append(code)
    return codes
