"""Q3, answered by the slice planner with the other reading: `#talk-resume` is an icon button.

The contract: «`#talk-resume` (прихована кнопка з текстом, бо дотик потрібен лише в цьому
рідкому випадку) поруч з `#talk`». The planner's answer to Q3 (ledger, 2026-10-27T12:29:58Z):
«Кнопка-значок з aria-label «Торкніться, щоб продовжити», без видимих слів: правило власника
задачі 207 ... важливіше за формулювання контракту; поведінка та сама — прихована, доки resume()
без дотику не допоміг». Rewritten by a fresh tester to that reading. The file keeps its name so
the seal's record of the held file is closed by this hand-in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic, set_language

T0 = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
H_ALICE = {"x-goog-iap-jwt-assertion": "tok-alice"}
TOKENS = {"tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"}}
LABEL = "Торкніться, щоб продовжити"


class Buttons(HTMLParser):
    """Every <button>: its attributes, the words inside it, whether an <svg> is inside it."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.found: list[dict[str, Any]] = []
        self._open: list[dict[str, Any]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "svg":
            for b in self._open:
                b["svg"] = True
        if tag == "button":
            b = {"attrs": dict(attrs), "text": "", "svg": False}
            self.found.append(b)
            self._open.append(b)

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._open:
            self._open.pop()

    def handle_data(self, data: str) -> None:
        for b in self._open:
            b["text"] += data


def test_Q3_talk_resume_is_a_hidden_icon_button_named_by_aria_label_without_words(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "o@example.com",
        }
    )
    identity = IapIdentity("aud", lambda token, audience: TOKENS[token])
    deps = Deps(store, identity, settings, lambda ctx: iter(()), lambda: T0, ScriptedSpeech(""))
    set_language(store, ALICE, "uk-UA")
    ref = TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))
    html = TestClient(create_app(deps)).get(f"/topics/{ref.uid}/{ref.topic_id}", headers=H_ALICE).text
    found = [b for b in Buttons(html).found if b["attrs"].get("id") == "talk-resume"]
    assert len(found) == 1, "no single #talk-resume button on the topic page"
    button = found[0]
    assert "hidden" in button["attrs"], "#talk-resume is not hidden on a fresh page"
    assert button["attrs"].get("aria-label") == LABEL, repr(button["attrs"].get("aria-label"))
    assert button["svg"], "#talk-resume carries no icon (<svg>)"
    assert " ".join(button["text"].split()) == "", f"#talk-resume shows words: {button['text']!r}"
