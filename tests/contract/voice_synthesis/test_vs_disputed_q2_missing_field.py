"""Disputed (Q2): `POST /speak` without the form field `text` at all is the 400 fragment, not 422."""

from pathlib import Path

from vs_fakes import ALICE, H_ALICE, NOT_ACCEPTED_TEXT, make_app

from thinkhow.platform.tts import ScriptedTts
from thinkhow.workspace import set_language


def test_q2_speak_without_the_text_field_is_400_fragment(tmp_path: Path) -> None:
    tts = ScriptedTts()
    app = make_app(tmp_path, tts)
    set_language(app.storage, ALICE, "uk-UA")
    r = app.client.post("/speak", data={}, headers=H_ALICE)
    assert r.status_code == 400
    assert NOT_ACCEPTED_TEXT in r.text
    assert tts.calls == []
