"""spoken-replies: the listening section and its rule in `facilitation/language.py` (slice tester; from the
contract's «Seam», not the code)."""

from pathlib import Path

from sr_fakes import LISTENING_HEAD

from thinkhow.facilitation import language

LISTENING_MD = Path(__file__).resolve().parents[3] / "src" / "thinkhow" / "facilitation" / "listening.md"


def test_listening_rule_when_spoken_is_newline_section_newline() -> None:
    section = language.LISTENING_SECTION
    assert section == LISTENING_MD.read_text(encoding="utf-8").rstrip("\n")
    assert section.startswith(LISTENING_HEAD + "\n")
    assert language.listening_rule(True) == "\n" + section + "\n"


def test_listening_rule_when_not_spoken_is_empty() -> None:
    assert language.listening_rule(False) == ""
