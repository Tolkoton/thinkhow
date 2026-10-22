"""The facilitator half of a card as text for the model's instruction (Ukrainian, A5).

The router half is left out: the router reads it (F5). Texts stand verbatim, line breaks included.
"""

from thinkhow.knowledge.schema import Card, Phase


def card_prompt(card: Card) -> str:
    """Flow: head → phases → ending, traps, what it pairs with."""
    half = card.facilitator
    parts = [
        f"# Картка: {card.title}",
        f"**Навіщо.** {half.purpose}",
        f"**Позиція ведучого.** {half.stance}",
        f"**Що потрібно на вході.** {half.needs}",
        "## Фази",
        *(_phase_text(phase) for phase in half.phases),
        f"## Чим закінчується\n{half.ending}",
        "## Пастки\n" + "\n".join(f"- **{trap.name}.** {trap.text}" for trap in half.traps),
        f"## Добре поєднується\n{half.pairs_well}",
    ]
    return "\n\n".join(parts) + "\n"


def _phase_text(phase: Phase) -> str:
    lines = [f"### {phase.id} — {phase.title}", f"- Мета: {phase.goal}"]
    lines += [f"- {item}" for item in phase.how]
    if phase.skip_if:
        lines.append(f"- Пропустити, якщо: {phase.skip_if}")
    lines.append(f"- Вихід: {phase.exit}")
    return "\n".join(lines)
