"""The person's language rule for the model (F13), shared by the facilitator and the router; and the rule
for a person who listens rather than reads (task 308)."""

from pathlib import Path

NO_LANGUAGE_RULE = "Ніколи не відповідай російською: на репліку російською відповідай українською."


def language_rule(language: str | None) -> str:
    """The person's language first, Russian never; with no language chosen, only the ban (F13, AC3)."""
    if language is None:
        return NO_LANGUAGE_RULE
    return (
        f"Відповідай мовою людини — {language}: цю мову вона обрала для розмов з ThinkHow, "
        "і це правило важливіше за «мовою останньої репліки» вище. "
        "Іншою мовою — лише якщо людина прямо попросить. "
        "Ніколи не відповідай російською — ні на репліку російською, ні на прохання."
    )


LISTENING_SECTION = (Path(__file__).with_name("listening.md")).read_text(encoding="utf-8").rstrip("\n")


def listening_rule(spoken: bool) -> str:
    """The section for a person who listens, right after the language rule; nothing when they read."""
    return f"\n{LISTENING_SECTION}\n" if spoken else ""
