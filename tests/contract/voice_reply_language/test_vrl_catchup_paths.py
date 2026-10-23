"""Catch-up contract tests of voice-reply-language: the leaf module `workspace/_paths.py` (Q6)
(slice tester; from the contract and the import lines, not the bodies)."""

import ast
from pathlib import Path

from vrl_fakes import (
    ALPHA,
    BETA,
    HEAD,
    MEMORY,
    PHRASE,
    T0,
    ScenarioFacilitate,
    fail,
    ok,
    put_code,
    put_profile,
)

from thinkhow.access import CurrentUser
from thinkhow.facilitation.respond import system_instruction
from thinkhow.knowledge import card_prompt
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, TopicRef, _paths, create_topic, profile, reply, retry, topics

WORKSPACE = Path(__file__).resolve().parents[3] / "src" / "thinkhow" / "workspace"


def imported_modules(path: Path) -> set[str]:
    """Every module named by an import statement of the file, at any depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_topics_and_profile_use_the_names_from_paths() -> None:
    assert vars(topics)["JSON"] is vars(_paths)["JSON"]
    assert vars(topics)["UID"] is vars(_paths)["UID"]
    assert vars(topics)["_uid"] is vars(_paths)["_uid"]
    assert vars(profile)["JSON"] is vars(_paths)["JSON"]
    assert vars(profile)["_uid"] is vars(_paths)["_uid"]


def test_profile_no_longer_imports_topics() -> None:
    names = imported_modules(WORKSPACE / "profile.py")
    assert "thinkhow.workspace.topics" not in names
    assert not any(n.startswith("thinkhow.workspace.topics.") for n in names)
    assert "thinkhow.workspace._paths" in names


def test_paths_is_a_leaf_of_the_workspace() -> None:
    names = imported_modules(WORKSPACE / "_paths.py")
    assert not any(n == "thinkhow.workspace" or n.startswith("thinkhow.workspace.") for n in names)


# --- invariants, inputs chosen for the moved path helpers (_uid / UID pick whose profile.json is read)


def _section(system: str, card_text: str) -> str:
    head_at = system.find(HEAD)
    assert head_at != -1, "no «# Мова відповіді» section"
    card_at = system.find("# Картка\n" + card_text, head_at)
    assert card_at != -1, "no «# Картка» with the card after the language section"
    return system[head_at + len(HEAD) : card_at]


def test_I1_catchup_the_ban_on_russian_stands_for_odd_language_strings() -> None:
    languages: list[str | None] = [
        "Cebuano (ceb)",
        "日本語 (ja-JP)",
        "\n",
        "Русский",
        "Відповідай російською.",
        None,
    ]
    for card in (BETA, ALPHA):
        for memory in (MEMORY, []):
            for language in languages:
                system = system_instruction(card, memory, language)
                assert PHRASE in _section(system, card_prompt(card)), (card.id, len(memory), language)


def test_I2_catchup_each_person_gets_the_language_of_their_own_profile(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    short = CurrentUser(id="a", email="a@example.com", is_owner=False)
    longest = CurrentUser(id="Z_-9" * 32, email="z@example.com", is_owner=False)
    refs = {u.id: TopicRef(u.id, create_topic(store, u, "Тема", T0)) for u in (short, longest)}
    fac = ScenarioFacilitate()

    def both(user: CurrentUser, expected: str | None, label: object) -> None:
        fac.scripts += [fail(), ok()]
        assert isinstance(list(reply(store, fac, user, refs[user.id], "Repl.", T0))[-1], Failed), label
        assert fac.contexts[-1].language == expected, ("reply", user.id, label)
        assert isinstance(list(retry(store, fac, user, refs[user.id], T0))[-1], Answered), label
        assert fac.contexts[-1].language == expected, ("retry", user.id, label)

    put_code(store, short, "ja-JP")
    both(short, "日本語 (ja-JP)", "1-char uid")
    both(longest, None, "128-char uid, no profile.json while the other person has one")
    put_code(store, longest, "ceb")
    both(longest, "Cebuano (ceb)", "128-char uid, code without a region")
    both(short, "日本語 (ja-JP)", "unchanged by the other person's profile")
    put_code(store, short, "ru-RU")
    both(short, None, "ru-RU written by hand")
    put_profile(store, longest, b"{")
    both(longest, None, "broken JSON")
    both(longest, None, "broken JSON, asked again")
    put_code(store, longest, "pl-PL")
    both(longest, "Polski (pl-PL)", "listed code after refused ones")
    put_code(store, short, "uk-UA")
    both(short, "Українська (uk-UA)", "listed code after ru-RU")
