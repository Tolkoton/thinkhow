"""Contract tests of voice-reply-language: `reply` and `retry` take the person's language from the profile
(slice tester; from the contract, not the code)."""

from pathlib import Path

from vrl_fakes import ALICE, T0, ScenarioFacilitate, fail, ok, put_code, put_profile

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, TopicRef, create_topic, reply, retry

ASK = "Chcę otworzyć kawiarnię."


def topic(store: LocalStorage) -> TopicRef:
    return TopicRef(ALICE.id, create_topic(store, ALICE, "Temat", T0))


def test_reply_passes_the_profile_language_as_name_with_code(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_code(store, ALICE, "pl-PL")
    fac = ScenarioFacilitate([ok()])
    events = list(reply(store, fac, ALICE, ref, ASK, T0))
    assert isinstance(events[-1], Answered)
    assert fac.contexts[0].language == "Polski (pl-PL)"


def test_reply_without_language_passes_none_and_does_not_fail(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_code(store, ALICE, "pl-PL")
    fac = ScenarioFacilitate([ok(), ok()])
    list(reply(store, fac, ALICE, ref, ASK, T0))
    put_profile(store, ALICE, b'{"email": "alice@example.com"}')
    events = list(reply(store, fac, ALICE, ref, "Dalej.", T0))
    assert isinstance(events[-1], Answered)
    assert [c.language for c in fac.contexts] == ["Polski (pl-PL)", None]


def test_retry_passes_the_profile_language_as_name_with_code(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_code(store, ALICE, "uk-UA")
    fac = ScenarioFacilitate([fail(), ok()])
    assert isinstance(list(reply(store, fac, ALICE, ref, ASK, T0))[-1], Failed)
    put_code(store, ALICE, "pl-PL")
    assert isinstance(list(retry(store, fac, ALICE, ref, T0))[-1], Answered)
    assert fac.contexts[1].language == "Polski (pl-PL)"


def test_retry_without_language_passes_none_and_does_not_fail(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_code(store, ALICE, "pl-PL")
    fac = ScenarioFacilitate([fail(), ok()])
    list(reply(store, fac, ALICE, ref, ASK, T0))
    put_profile(store, ALICE, b'{"email": "alice@example.com"}')
    events = list(retry(store, fac, ALICE, ref, T0))
    assert isinstance(events[-1], Answered)
    assert [c.language for c in fac.contexts] == ["Polski (pl-PL)", None]


def test_reply_reads_the_language_at_the_call_not_at_the_first_step(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_code(store, ALICE, "pl-PL")
    fac = ScenarioFacilitate([ok()])
    events = reply(store, fac, ALICE, ref, ASK, T0)
    put_code(store, ALICE, "de-DE")
    list(events)
    assert fac.contexts[0].language == "Polski (pl-PL)"


def test_retry_reads_the_language_at_the_call_not_at_the_first_step(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = topic(store)
    put_code(store, ALICE, "de-DE")
    fac = ScenarioFacilitate([fail(), ok()])
    list(reply(store, fac, ALICE, ref, ASK, T0))
    put_code(store, ALICE, "pl-PL")
    events = retry(store, fac, ALICE, ref, T0)
    put_code(store, ALICE, "de-DE")
    list(events)
    assert fac.contexts[1].language == "Polski (pl-PL)"
