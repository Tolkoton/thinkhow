"""Live tracer of slice research-quick (`-m live`): the owner's turn #17 with web search, real model on `eu`.

The owner's topic t-d824f508a729 is read at run time from the users bucket (ADC) — its text never enters
the repository. Turns #1–#16 (one session) go into a local topic with the card `weighted-matrix` chosen,
then the owner's #17 goes through `workspace.reply` with `VertexLlm(search=True)`. Recorded as well, not
conditions: the owner's #25 after #1–#24, and a direct price question after #1–#16. One run; no search on
#17 is a finding, not a reason to run again. Each run writes a new file in .engine/artifacts/spikes/ with
the model's answers, the queries, the sources and the `llm_call` lines — the owner's turns only by number.
Slice research-display: no Google redirect link may stay where Google answers a redirect, and the topic page
shows the links and the Search suggestions frame under the answer to #17.
"""

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.links import GOOGLE_REDIRECT
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.app import build_deps
from thinkhow.web.server import create_app
from thinkhow.workspace import Answered, Delta, TopicRef, set_language
from thinkhow.workspace import conversation as conv_file

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
SPIKES = ROOT / ".engine" / "artifacts" / "spikes"
OWNER_URI = "gs://pocket-lawyer-431614-thinkhow-users/104839836105981044615/t-d824f508a729/conversation.md"
CARD = "weighted-matrix"
PRICE = "Скільки зараз коштує новий Škoda Octavia Combi у Німеччині?"
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)


def _owner_conversation() -> conv_file.Conversation:
    text = subprocess.run(["gcloud", "storage", "cat", OWNER_URI], capture_output=True, check=True, text=True)
    return conv_file.parse(text.stdout)


def _topic(
    storage: LocalStorage, owner: conv_file.Conversation, upto: int, name: str, rev: dict[str, int]
) -> TopicRef:
    """A local topic holding the owner's turns #1..upto, with the card chosen on the first turn."""
    ref = TopicRef(USER.id, "t-" + name.ljust(12, "0")[:12])
    turns = [t for s in owner.sessions for t in s.turns if t.no <= upto]
    conv = conv_file.Conversation(owner.title, [conv_file.SessionDoc(no=1, turns=turns)])
    base = f"{ref.uid}/{ref.topic_id}"
    storage.write("users", f"{base}/conversation.md", conv_file.render(conv).encode(), "text/markdown")
    choose = {
        "turn": 1,
        "rev": rev,
        "kind": "choose",
        "profile": None,
        "candidates": [],
        "card_id": CARD,
        "end": None,
        "why": "live tracer: the card of the spike",
    }
    storage.write(
        "users", f"{base}/routing.json", json.dumps({"decisions": [choose]}).encode(), "application/json"
    )
    return ref


def _turn(owner: conv_file.Conversation, no: int) -> conv_file.Turn:
    return next(t for s in owner.sessions for t in s.turns if t.no == no)


def _ask(storage: LocalStorage, facilitate: Any, ref: TopicRef, text: str, at: Any) -> dict[str, Any]:
    from thinkhow.workspace import reply

    events = list(reply(storage, facilitate, USER, ref, text, at + timedelta(seconds=30)))
    base = f"{ref.uid}/{ref.topic_id}"
    research = json.loads(storage.read("users", f"{base}/research.json") or b'{"entries": []}')
    problem_map = json.loads(storage.read("users", f"{base}/map.json") or b"{}")
    return {
        "ref": ref,
        "turn": events[-1].turn_no if isinstance(events[-1], Answered) else None,
        "answered": isinstance(events[-1], Answered),
        "answer": "".join(e.text for e in events if isinstance(e, Delta)),
        "research": research["entries"],
        "facts": [i["text"] for i in problem_map.get("items", []) if i["type"] == "fact"],
    }


def _section(title: str, row: dict[str, Any]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        f"answered: {row['answered']}",
        "",
        "Відповідь моделі:",
        "",
        row["answer"],
        "",
    ]
    for entry in row["research"]:
        lines += [f"- запити: {entry['queries']}", f"- джерела: {[s['url'] for s in entry['sources']]}"]
        lines += [f"- Search suggestions: {len(entry['suggestions_html'] or '')} символів"]
    return [*lines, f"- пункти fact у карті: {row['facts']}", ""]


@pytest.mark.live
def test_owner_turn_17_searches_and_answers_with_sources(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    storage = LocalStorage(tmp_path)
    seed(storage, CARDS)
    knowledge = current(storage)
    rev = {"rev": knowledge.rev, "n": knowledge.n}
    environ = {
        **os.environ,
        "THINKHOW_LOCAL": "false",
        "THINKHOW_USERS_BUCKET": "-",
        "THINKHOW_SYSTEM_BUCKET": "-",
        "THINKHOW_OWNER_EMAIL": "-",
    }
    llm = make_llm(load_settings(environ), lambda *_: "", search=True)

    def facilitate(ctx: Any) -> Any:
        return respond(ctx, knowledge, llm)

    set_language(storage, USER, "uk-UA")
    owner = _owner_conversation()
    t17, t25 = _turn(owner, 17), _turn(owner, 25)
    r17 = _ask(storage, facilitate, _topic(storage, owner, 16, "a17", rev), t17.text, t17.at)
    r25 = _ask(storage, facilitate, _topic(storage, owner, 24, "b25", rev), t25.text, t25.at)
    price = _ask(storage, facilitate, _topic(storage, owner, 16, "c00", rev), PRICE, t17.at)
    out = capfd.readouterr().out
    log = [line for line in out.splitlines() if '"llm_call"' in line]
    lines = ["# Live tracer research-quick (task 303, S1)", "", f"Run: {_now()}", ""]
    lines += _section("Репліка власника #17 (історія #1–#16, картка weighted-matrix)", r17)
    lines += _section("Репліка власника #25 (історія #1–#24) — записується", r25)
    lines += _section(f"Пряме питання «{PRICE}» (історія #1–#16) — записується", price)
    left = _google_links(r17) + _google_links(price)
    page = _page(tmp_path, r17)
    lines += ["## S1b: розгортання і сторінка", "", f"посилань Google лишилось: {left}", ""]
    lines += [f'на сторінці теми #17: `<a href="https://` — {page.count('<a href="https://')}']
    lines += [
        f'`<iframe class="search-suggestions"` після #{r17["turn"]}: {_frame_after(page, r17["turn"])}',
        "",
    ]
    for entry in r17["research"]:
        lines += [
            "Search suggestions (HTML, як прийшов):",
            "",
            "```html",
            entry["suggestions_html"] or "",
            "```",
            "",
        ]
    lines += ["## Рядки `llm_call`", "", "```", *log, "```", ""]
    path = SPIKES / f"research-display-live-{_now().replace(':', '')}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(out, end="")
    print(path)
    assert r17["answered"], r17
    assert "\n\nДжерела: [" in r17["answer"], r17["answer"]
    assert r17["research"] and r17["research"][0]["queries"] and r17["research"][0]["sources"], r17[
        "research"
    ]
    for status in left:  # a Google link still there: Google must not have answered with a redirect
        assert not (300 <= status[1] < 400 and str(status[2]).startswith("http")), left
    assert '<a href="https://' in page and _frame_after(page, r17["turn"]), page[-2000:]
    first = json.loads(log[0])  # the first model call of the run is #17's facilitator call
    assert first["search"] is True and first["queries"] >= 1, log


def _google_links(row: dict[str, Any]) -> list[tuple[str, int, str | None]]:
    """Every source still a Google redirect link, with what a direct HEAD answers for it now."""
    urls = [s["url"] for e in row["research"] for s in e["sources"] if s["url"].startswith(GOOGLE_REDIRECT)]
    return [(u, *_head(u)) for u in urls]


def _head(url: str) -> tuple[int, str | None]:
    try:
        response = httpx.head(url, follow_redirects=False, timeout=10)
    except httpx.HTTPError as exc:
        return 0, type(exc).__name__
    return response.status_code, response.headers.get("location")


def _page(root: Path, row: dict[str, Any]) -> str:
    """The topic page of #17's local topic, as the owner of the local app sees it."""
    environ = {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(root),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
    client = TestClient(create_app(build_deps(environ, CARDS)), follow_redirects=False)
    client.post("/language", data={"code": "uk-UA"})
    ref = row["ref"]
    return client.get(f"/topics/{ref.uid}/{ref.topic_id}").text


def _frame_after(page: str, turn: int | None) -> bool:
    start = page.find(f'id="t{turn}"')
    nxt = page.find(f'id="t{(turn or 0) + 1}"')
    frame = page.find('<iframe class="search-suggestions"', start)
    return start >= 0 and frame > start and (nxt < 0 or frame < nxt)


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
