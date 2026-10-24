"""Catch-up contract tests of cards-library: the smoke script (slice tester).

Written from the contract (.engine/slices/cards-library.md, «Exit criterion», the smoke line), not the
code. The script is run as a process from the repository root and judged by its exit code and by what it
leaves behind: revision 1 is seeded «в процесі скрипта» into «<тимчасова тека>», and the Job process gets
«THINKHOW_LOCAL_DIR=<тимчасова тека>» — never the repository, never a folder inherited from the caller.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "smoke_test_cards_library.py"
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"}


def run_smoke(tmp: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp))
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def change_records_in_repo() -> set[Path]:
    found: set[Path] = set()
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        here = Path(root)
        if here.name == "changes" and here.parent.name == "knowledge":
            found.update(here / f for f in files)
    return found


def cards_snapshot() -> dict[str, str]:
    return {p.name: hashlib.sha1(p.read_bytes()).hexdigest() for p in sorted((REPO / "cards").iterdir())}


def files_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def test_smoke_runs_from_the_repository_root_and_exits_0(tmp_path: Path) -> None:
    result = run_smoke(tmp_path)
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_smoke_leaves_the_repository_cards_and_knowledge_untouched(tmp_path: Path) -> None:
    changes_before = change_records_in_repo()
    cards_before = cards_snapshot()
    result = run_smoke(tmp_path)
    assert result.returncode == 0, result.stderr
    assert change_records_in_repo() == changes_before, "the smoke wrote Knowledge into the repository"
    assert cards_snapshot() == cards_before, "the smoke changed the repository's cards/"


def test_smoke_gives_the_job_its_own_temporary_folder_not_an_inherited_local_dir(tmp_path: Path) -> None:
    decoy = tmp_path / "decoy-local-dir"
    decoy.mkdir()
    work = tmp_path / "tmp"
    work.mkdir()
    result = run_smoke(work, {"THINKHOW_LOCAL": "1", "THINKHOW_LOCAL_DIR": str(decoy)})
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert files_under(decoy) == [], (
        "the smoke used THINKHOW_LOCAL_DIR of its caller, not its temporary folder"
    )
