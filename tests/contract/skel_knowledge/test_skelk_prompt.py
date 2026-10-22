"""Contract tests of skel-knowledge: prompt.py (slice tester; written from the contract, not the code)."""

from skelk_fakes import card_dict, phase_dict

from thinkhow.knowledge import Card, card_prompt


def test_card_prompt_carries_every_part_of_the_facilitator_half() -> None:
    card = Card.model_validate(
        card_dict(
            "c",
            title="Назва-картки-X",
            phases=[
                phase_dict("p_one", skip_if="пропустити-якщо-маркер"),
                phase_dict("p_two"),
            ],
        )
    )
    text = card_prompt(card)
    expected = [
        "Назва-картки-X",
        "навіщо c",
        "позиція c",
        "на вході c",
        "p_one",
        "Фаза P_ONE",
        "мета фази P_ONE",
        "як-1 фази P_ONE",
        "як-2 фази P_ONE",
        "пропустити-якщо-маркер",
        "вихід фази P_ONE",
        "p_two",
        "Фаза P_TWO",
        "мета фази P_TWO",
        "як-1 фази P_TWO",
        "як-2 фази P_TWO",
        "вихід фази P_TWO",
        "чим закінчується c",
        "пастка-назва c",
        "пастка-текст c",
        "поєднується c",
    ]
    missing = [part for part in expected if part not in text]
    assert missing == []


def test_card_prompt_has_no_router_half() -> None:
    card = Card.model_validate(card_dict("c"))
    text = card_prompt(card)
    assert "роутер-" not in text


def test_I3_every_phase_id_and_exit_is_in_card_prompt() -> None:
    long_exit = "довгий вихід " + "слово " * 600 + "кінець-довгого-виходу"
    cases = [
        # one phase only (the smallest lawful card)
        [phase_dict("a", exit_text="єдиний вихід")],
        # phases with and without skip_if; a very long exit; an id of 64 characters
        [
            phase_dict("with_skip", exit_text="вихід зі skip_if", skip_if="пропустити, якщо вже є"),
            phase_dict("no_skip", exit_text="вихід без skip_if"),
            phase_dict("long_exit", exit_text=long_exit),
            phase_dict("x" * 64, exit_text="вихід фази з довгим id"),
        ],
        # many phases, every one skippable, exits with markdown-like characters
        [
            phase_dict(f"step_{i:02d}", exit_text=f"**вихід** #{i} «{i}» — `{i}`", skip_if=f"якщо {i}")
            for i in range(12)
        ],
        # two phases with the same exit text
        [
            phase_dict("twin_1", exit_text="той самий вихід"),
            phase_dict("twin_2", exit_text="той самий вихід"),
        ],
    ]
    for phases in cases:
        card = Card.model_validate(card_dict("c", phases=phases))
        text = card_prompt(card)
        for phase in phases:
            assert phase["id"] in text, phase["id"]
            assert phase["exit"] in text, phase["id"]
