"""DISPUTED (Q1): I3's «Domain» is any valid Card, and a valid exit may hold a line break.
The reading taken: the exit stands in `card_prompt` verbatim, line breaks included
(no re-wrapping, no indenting of the second line). Not sealed until answered."""

from skelk_fakes import card_dict, phase_dict

from thinkhow.knowledge import Card, card_prompt


def test_q1_a_multiline_exit_stands_verbatim_in_card_prompt() -> None:
    exit_text = "перший рядок виходу\nдругий рядок виходу"
    card = Card.model_validate(card_dict("c", phases=[phase_dict("p_one", exit_text=exit_text)]))
    assert exit_text in card_prompt(card)
