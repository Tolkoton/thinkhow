"""Contract tests of skel-guards-deploy: the new guards and `tests/test_ac4.py` exist and are green
on today's tree (slice tester; from the contract). Each runs the named test by its id in a subprocess.
"""

import re

from skelgd_files import ROOT, run_pytest

GUARDS = "tests/test_a3_guards.py"


def _green(test_id: str) -> None:
    file = test_id.split("::")[0]
    assert (ROOT / file).is_file(), f"{file} does not exist"
    done = run_pytest(test_id)
    assert done.returncode == 0, done.stdout[-2000:]
    assert re.search(r"\b1 passed\b", done.stdout), done.stdout[-2000:]


def test_users_guard_exists_and_passes_on_the_tree() -> None:
    _green(f"{GUARDS}::test_users_paths_are_built_only_by_workspace")


def test_knowledge_guard_exists_and_passes_on_the_tree() -> None:
    _green(f"{GUARDS}::test_knowledge_files_are_written_only_by_knowledge")


def test_planted_breach_test_exists_and_passes() -> None:
    _green(f"{GUARDS}::test_the_guards_see_a_planted_breach")


def test_ac4_holds_at_least_four_tests_and_all_pass() -> None:
    assert (ROOT / "tests/test_ac4.py").is_file(), "tests/test_ac4.py does not exist"
    done = run_pytest("tests/test_ac4.py")
    assert done.returncode == 0, done.stdout[-2000:]
    match = re.search(r"\b(\d+) passed\b", done.stdout)
    assert match is not None and int(match.group(1)) >= 4, done.stdout[-2000:]
