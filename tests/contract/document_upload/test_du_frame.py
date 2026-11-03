"""Contract tests of document-upload: `facilitation.types.document_turn` — the turn as the model reads it.

Slice tester; from the contract `.engine/slices/document-upload.md`, not the code. The wording of the
frame is the builder's; the tests pin its shape: a header naming the document,
the text verbatim between a begin and an end line, and the ask after them.
"""

NAME = "Резюме-Олени.pdf"
TEXT = "Олена Коваль\nДосвід: Monobank, 5 років\n\nНавички: SQL"


def _frame(name: str, text: str) -> str:
    from thinkhow.facilitation.types import document_turn

    return document_turn(name, text)


def test_the_frame_names_the_document_then_holds_the_text_between_a_begin_and_an_end_line_then_asks() -> None:
    out = _frame(NAME, TEXT)
    block = "\n" + TEXT + "\n"
    assert block in out, out
    at = out.index(block)
    before, after = out[:at], out[at + len(block) :]
    assert NAME in before, out  # the header names the document before the text
    begin = before.rsplit("\n", 1)[-1]
    assert begin.strip(), f"no begin line right before the text: {out!r}"
    end, _, ask = after.partition("\n")
    assert end.strip(), f"no end line right after the text: {out!r}"
    assert ask.strip(), f"no ask after the end line: {out!r}"


def test_the_frame_is_a_plain_function_of_its_two_values() -> None:
    assert _frame(NAME, TEXT) == _frame(NAME, TEXT)
    other_text = _frame(NAME, "Зовсім інший текст")
    other_name = _frame("cv.docx", TEXT)
    assert "Зовсім інший текст" in other_text and TEXT not in other_text
    assert "cv.docx" in other_name and NAME not in other_name
