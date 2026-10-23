"""Block tests of voice-and-language (F13): one per line of «Inter-slice contracts», one per acceptance
criterion (the feature closes with S3).

Slice tester, mode `block`; from `.engine/architecture/feature/voice-and-language.md` and the public
signatures, not the bodies. Every test drives two or more slices together through the seam its line names.
Expected values are written by hand from the artifact and the slice contracts it names.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from vab_fakes import (
    ALICE,
    AUDIO,
    CARDS,
    H_ALICE,
    REPO,
    T0,
    WEBM,
    FakeFacilitate,
    RecordingLlm,
    RecordingSpeech,
    local_environ,
    make_app,
    profile,
    sse_events,
)

import thinkhow.web.local as web_local
from thinkhow import knowledge, workspace
from thinkhow.facilitation import respond
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitationError,
    FacilitatorUpdate,
    ReplyDelta,
)
from thinkhow.platform.llm import ScriptedLlm
from thinkhow.platform.speech import SpeechUnavailable
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.app import build_deps
from thinkhow.web.server import create_app

POLISH = "Polski (pl-PL)"
UKRAINIAN = "Українська (uk-UA)"
ENGLISH_US = "English (United States) (en-US)"
SECTION = "# Мова відповіді"
NEVER_RUSSIAN = "Ніколи не відповідай російською"
FIRST_CHOOSE = "Спершу оберіть мову"
NOT_RECOGNIZED = "Не вдалося розпізнати — спробуйте ще раз."
LOCAL_TEXT = "(локальний режим) розпізнаний текст"


def drain[T](events: Iterator[T]) -> list[T]:
    return list(events)


def new_ref(store: LocalStorage, title: str = "Тема") -> workspace.TopicRef:
    workspace.ensure_profile(store, ALICE)
    return workspace.TopicRef(ALICE.id, workspace.create_topic(store, ALICE, title, T0))


def write_profile_by_hand(store: LocalStorage, data: dict[str, object]) -> None:
    store.write("users", f"{ALICE.id}/profile.json", json.dumps(data).encode(), "application/json")


# ------------------------------------------------------------------ Inter-slice contracts


# S1 → S2: the code S1 stores is the code S2 hands to platform.speech
def test_s1_to_s2_transcribe_passes_the_code_set_by_set_language_to_speech(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    ref = new_ref(store)
    speech = RecordingSpeech(text="Dzień dobry")

    workspace.set_language(store, ALICE, "pl-PL")
    assert workspace.language(store, ALICE) == workspace.Language(code="pl-PL", name="Polski")
    assert workspace.transcribe(store, speech, ALICE, ref, AUDIO, WEBM) == "Dzień dobry"

    workspace.set_language(store, ALICE, "cmn-Hans-CN")  # a code of three parts goes as it is
    workspace.transcribe(store, speech, ALICE, ref, AUDIO, WEBM)

    assert speech.calls == [(AUDIO, WEBM, "pl-PL"), (AUDIO, WEBM, "cmn-Hans-CN")]


# S1 → S2: no language (or one outside the list) is S1's NoLanguage, and speech is not called
def test_s1_to_s2_transcribe_without_a_listed_language_raises_s1_nolanguage(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    ref = new_ref(store)
    speech = RecordingSpeech()

    with pytest.raises(workspace.NoLanguage):
        workspace.transcribe(store, speech, ALICE, ref, AUDIO, WEBM)  # profile with email only

    write_profile_by_hand(store, {"email": ALICE.email, "language": "ru-RU"})
    with pytest.raises(workspace.NoLanguage):
        workspace.transcribe(store, speech, ALICE, ref, AUDIO, WEBM)

    assert speech.calls == []


# S1 → S2 (web): NoLanguage on the voice route is 409 «Спершу оберіть мову»; after POST /language it works
def test_s1_to_s2_web_voice_without_language_is_409_then_works_after_choosing(tmp_path: Path) -> None:
    speech = RecordingSpeech(text="Dzień dobry")
    app = make_app(tmp_path, speech)
    ref = new_ref(app.storage)
    url = f"/topics/{ref.uid}/{ref.topic_id}/voice"

    refused = app.client.post(url, content=AUDIO, headers={**H_ALICE, "Content-Type": WEBM})
    assert refused.status_code == 409
    assert FIRST_CHOOSE in refused.text
    assert "location" not in refused.headers
    assert speech.calls == []

    chosen = app.client.post("/language", data={"code": "pl-PL"}, headers=H_ALICE)
    assert chosen.status_code == 303
    done = app.client.post(url, content=AUDIO, headers={**H_ALICE, "Content-Type": WEBM})
    assert done.status_code == 200
    assert done.json() == {"text": "Dzień dobry"}
    assert speech.calls == [(AUDIO, WEBM, "pl-PL")]


@dataclass
class FailFirst:
    """A facilitate that fails its first call (so `retry` has something to answer), then answers."""

    contexts: list[FacilitationContext] = field(default_factory=list)
    inner: FakeFacilitate = field(default_factory=FakeFacilitate)

    def __call__(self, ctx: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        self.contexts.append(ctx)
        if len(self.contexts) == 1:
            raise FacilitationError("planned")
        yield from self.inner(ctx)


# S1 → S3: the same language(...) reaches FacilitationContext.language as f"{name} ({code})"
def test_s1_to_s3_reply_and_retry_carry_name_with_code_of_the_profile(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    ref = new_ref(store)
    facilitate = FailFirst()

    workspace.set_language(store, ALICE, "pl-PL")
    events = drain(workspace.reply(store, facilitate, ALICE, ref, "Chcę otworzyć kawiarnię.", T0))
    assert any(isinstance(e, workspace.Failed) for e in events)

    workspace.set_language(store, ALICE, "en-US")
    drain(workspace.retry(store, facilitate, ALICE, ref, T0))

    assert [c.language for c in facilitate.contexts] == [POLISH, ENGLISH_US]


# ------------------------------------------------------------------ Acceptance criteria


def test_ac1_first_entry_chooses_language_change_it_and_russian_is_neither_listed_nor_accepted(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path, RecordingSpeech())
    c = app.client

    first = c.get("/", headers=H_ALICE)
    assert first.status_code == 303
    assert first.headers["location"].endswith("/language")

    page = c.get("/language", headers=H_ALICE)
    assert page.status_code == 200
    assert '<select name="code"' in page.text
    assert 'value="uk-UA"' in page.text
    assert not re.search(r'value="ru[-"]', page.text, flags=re.I)

    before = profile(app.storage, ALICE)
    refused = c.post("/language", data={"code": "ru-RU"}, headers=H_ALICE)
    assert refused.status_code == 400
    assert profile(app.storage, ALICE) == before

    assert c.post("/language", data={"code": "uk-UA"}, headers=H_ALICE).status_code == 303
    assert c.get("/", headers=H_ALICE).status_code == 200
    assert c.post("/language", data={"code": "pl-PL"}, headers=H_ALICE).status_code == 303
    saved = profile(app.storage, ALICE)
    assert saved is not None
    assert saved["language"] == "pl-PL"
    assert saved["email"] == ALICE.email


def test_ac2_microphone_on_the_topic_page_and_recognition_in_the_persons_language_can_be_repeated(
    tmp_path: Path,
) -> None:
    speech = RecordingSpeech(text="Хочу відкрити кав'ярню.", fail_first=[SpeechUnavailable("planned")])
    app = make_app(tmp_path, speech)
    c = app.client
    assert c.post("/language", data={"code": "uk-UA"}, headers=H_ALICE).status_code == 303
    topic = c.post("/topics", data={"title": "Кав'ярня"}, headers=H_ALICE).headers["location"]

    page = c.get(topic, headers=H_ALICE)
    assert page.status_code == 200
    assert 'id="mic"' in page.text
    assert 'id="recognize"' in page.text

    failed = c.post(f"{topic}/voice", content=AUDIO, headers={**H_ALICE, "Content-Type": WEBM})
    assert failed.status_code == 502
    assert NOT_RECOGNIZED in failed.text

    again = c.post(f"{topic}/voice", content=AUDIO, headers={**H_ALICE, "Content-Type": WEBM})
    assert again.status_code == 200
    assert again.json() == {"text": "Хочу відкрити кав'ярню."}
    assert speech.calls == [(AUDIO, WEBM, "uk-UA"), (AUDIO, WEBM, "uk-UA")]


def test_ac3_the_model_is_told_the_persons_language_and_never_russian_through_the_web(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path / "data")
    assert knowledge.seed(store, CARDS) is True
    llm = RecordingLlm(ScriptedLlm(web_local.local_script))
    facilitate = functools.partial(respond, knowledge=knowledge.current(store), llm=llm)
    app = make_app(tmp_path, RecordingSpeech(), facilitate=facilitate, storage=store)
    c = app.client

    assert c.post("/language", data={"code": "pl-PL"}, headers=H_ALICE).status_code == 303
    topic = c.post("/topics", data={"title": "Kawiarnia"}, headers=H_ALICE).headers["location"]
    first = sse_events(c.post(f"{topic}/reply", data={"text": "Что мне делать?"}, headers=H_ALICE).text)
    assert first[-1][0] == "answered"
    polish = list(llm.systems)
    assert polish
    for system in polish:
        assert SECTION in system
        section = system[system.index(SECTION) : system.index("# Картка")]
        assert POLISH in section
        assert NEVER_RUSSIAN in section

    assert c.post("/language", data={"code": "uk-UA"}, headers=H_ALICE).status_code == 303
    second = sse_events(c.post(f"{topic}/reply", data={"text": "Ещё вопрос."}, headers=H_ALICE).text)
    assert second[-1][0] == "answered"
    ukrainian = llm.systems[len(polish) :]
    assert ukrainian
    for system in ukrainian:
        section = system[system.index(SECTION) : system.index("# Картка")]
        assert UKRAINIAN in section
        assert POLISH not in section
        assert NEVER_RUSSIAN in section


def test_ac4_locally_choose_language_dictate_and_send(tmp_path: Path) -> None:
    deps = build_deps(local_environ(tmp_path), CARDS)
    c = TestClient(create_app(deps), follow_redirects=False, raise_server_exceptions=False)

    first = c.get("/")
    assert first.status_code == 303
    assert first.headers["location"].endswith("/language")
    assert c.post("/language", data={"code": "uk-UA"}).status_code == 303
    assert c.get("/").status_code == 200

    topic = c.post("/topics", data={"title": "Локально"}).headers["location"]
    assert 'id="mic"' in c.get(topic).text
    voice = c.post(f"{topic}/voice", content=AUDIO, headers={"Content-Type": WEBM})
    assert voice.status_code == 200
    assert voice.json() == {"text": LOCAL_TEXT}

    sent = sse_events(c.post(f"{topic}/reply", data={"text": voice.json()["text"]}).text)
    assert sent[0] == ("saved", {"turn": 1})
    assert sent[-1] == ("answered", {"turn": 2})


def test_ac5_adr_names_the_model_and_the_measured_time_to_text() -> None:
    adrs = sorted((REPO / "docs" / "adr").glob("0005-*.md"))
    assert len(adrs) == 1
    text = adrs[0].read_text(encoding="utf-8")
    assert "gemini-3.5-transcribe" in text
    assert re.search(r"\d+(?:\.\d+)?\s*с\b", text), "no measured time to text (seconds) in the ADR"
    assert "Chirp 3" in text  # the ADR says what was not compared and why


def test_ac6_deploy_checklist_tells_the_owner_to_check_voice_and_language() -> None:
    text = (REPO / "docs" / "deploy.md").read_text(encoding="utf-8")
    assert "Говорити" in text  # the microphone button the owner presses on the deployment
    assert "Мова" in text  # the language page
    assert "speech_call" in text  # what the journal must show after a dictation
