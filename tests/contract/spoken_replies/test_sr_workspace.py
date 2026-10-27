"""spoken-replies: the flag goes from `workspace.reply` / `retry` into `FacilitationContext` and is written
nowhere (slice tester; Seam 3 of «Hardest seams», workspace half)."""

from pathlib import Path

from sr_fakes import ALICE, T0, ScenarioFacilitate, fail, ok, rich, snapshot

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Failed, TopicRef, create_topic, reply, retry


def new_topic(store: LocalStorage) -> TopicRef:
    return TopicRef(ALICE.id, create_topic(store, ALICE, "Тема", T0))


def test_reply_passes_spoken_into_the_context(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = new_topic(store)
    fac = ScenarioFacilitate(scripts=[ok(), ok(), ok()])
    assert isinstance(list(reply(store, fac, ALICE, ref, "Перше.", T0, spoken=True))[-1], Answered)
    assert fac.contexts[-1].spoken is True
    assert isinstance(list(reply(store, fac, ALICE, ref, "Друге.", T0, spoken=False))[-1], Answered)
    assert fac.contexts[-1].spoken is False
    assert isinstance(list(reply(store, fac, ALICE, ref, "Третє.", T0))[-1], Answered)
    assert fac.contexts[-1].spoken is False


def test_retry_passes_spoken_into_the_context(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    ref = new_topic(store)
    fac = ScenarioFacilitate()
    for flag in (True, False, None):
        fac.scripts += [fail(), ok()]
        assert isinstance(list(reply(store, fac, ALICE, ref, "Репліка.", T0))[-1], Failed), flag
        kw = {} if flag is None else {"spoken": flag}
        assert isinstance(list(retry(store, fac, ALICE, ref, T0, **kw))[-1], Answered), flag
        assert fac.contexts[-1].spoken is (flag is True), flag


def test_the_flag_is_written_nowhere(tmp_path: Path) -> None:
    files: dict[bool, dict[str, bytes]] = {}
    for spoken in (True, False):
        root = tmp_path / str(spoken)
        store = LocalStorage(root)
        ref = new_topic(store)
        fac = ScenarioFacilitate(scripts=[rich(1), fail(), rich(2)])
        assert isinstance(
            list(reply(store, fac, ALICE, ref, "Скільки коштує?", T0, spoken=spoken))[-1], Answered
        )
        assert isinstance(list(reply(store, fac, ALICE, ref, "А ще?", T0, spoken=spoken))[-1], Failed)
        assert isinstance(list(retry(store, fac, ALICE, ref, T0, spoken=spoken))[-1], Answered)
        assert [c.spoken for c in fac.contexts] == [spoken] * 3
        files[spoken] = {
            path.replace(ref.topic_id, "<topic>"): data.replace(ref.topic_id.encode(), b"<topic>")
            for path, data in snapshot(root).items()
        }
    names = {Path(p).name for p in files[True]}
    assert {"conversation.md", "map.json", "routing.json", "research.json"} <= names, sorted(names)
    assert files[True] == files[False]
