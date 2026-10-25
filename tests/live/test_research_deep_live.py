"""Live tracer of slice research-deep (`-m live`): one deep research end to end on the real Google `eu`.

The owner's topic t-d824f508a729 is read at run time from the users bucket (ADC); its text never enters
the repository. Turns #1–#16 go into a local topic with the card `weighted-matrix` chosen, the model's #16
replaced by an offer of deep research; the person answers «Так, досліди.». Conditions (AC3): steps, report
and sources line in the answer; a `deep` entry in research.json; time, tokens, queries and price in the
output file. One run: red means the slice is not closed, never a rerun unchanged.
"""

import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from thinkhow.access import CurrentUser
from thinkhow.facilitation import respond
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, TopicRef, reply, set_language
from thinkhow.workspace import conversation as conv_file

ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "cards"
SPIKES = ROOT / ".engine" / "artifacts" / "spikes"
OWNER_URI = "gs://pocket-lawyer-431614-thinkhow-users/104839836105981044615/t-d824f508a729/conversation.md"
OFFER = (
    "Можу глибше дослідити, як Mittelstand купує консалтинг і де швидше перші гроші — "
    "це близько двох хвилин. Шукати?"
)
YES = "Так, досліди."
USER = CurrentUser(id="live-person", email="live@example.com", is_owner=False)
IN_USD, OUT_USD, QUERY_USD = (
    2.2 / 1e6,
    11 / 1e6,
    14 / 1000,
)  # PR-19: the Vertex price list, search beyond 5 000


def _topic(storage: LocalStorage, rev: dict[str, int]) -> tuple[TopicRef, datetime]:
    text = subprocess.run(["gcloud", "storage", "cat", OWNER_URI], capture_output=True, check=True, text=True)
    owner = conv_file.parse(text.stdout)
    turns = [t for s in owner.sessions for t in s.turns if t.no <= 16]
    turns[-1] = conv_file.Turn(16, "model", turns[-1].at, OFFER)
    ref = TopicRef(USER.id, "t-dee900000000")
    base = f"{ref.uid}/{ref.topic_id}"
    conv = conv_file.Conversation(owner.title, [conv_file.SessionDoc(no=1, turns=turns)])
    storage.write("users", f"{base}/conversation.md", conv_file.render(conv).encode(), "text/markdown")
    choose = {
        "turn": 1,
        "rev": rev,
        "kind": "choose",
        "profile": None,
        "candidates": [],
        "card_id": "weighted-matrix",
        "end": None,
        "why": "live tracer: the card of the spike",
    }
    storage.write(
        "users", f"{base}/routing.json", json.dumps({"decisions": [choose]}).encode(), "application/json"
    )
    return ref, turns[-1].at


def _price(log: list[dict[str, Any]]) -> tuple[float, float, int]:
    model = sum(
        c["prompt_tokens"] * IN_USD + (c["output_tokens"] + c["thought_tokens"]) * OUT_USD for c in log
    )
    queries = sum(c["queries"] for c in log)
    return model, queries * QUERY_USD, queries


@pytest.mark.live
def test_one_deep_research_end_to_end(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
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
    ref, at = _topic(storage, rev)
    started = time.monotonic()
    events = list(reply(storage, facilitate, USER, ref, YES, at + timedelta(minutes=1)))
    total_s = time.monotonic() - started
    base = f"{ref.uid}/{ref.topic_id}"
    answer = "".join(e.text for e in events if isinstance(e, Delta))
    research = json.loads(storage.read("users", f"{base}/research.json") or b'{"entries": []}')["entries"]
    deep = [e for e in research if e["depth"] == "deep"]
    problem_map = json.loads(storage.read("users", f"{base}/map.json") or b"{}")
    routing = json.loads(storage.read("users", f"{base}/routing.json") or b'{"decisions": []}')["decisions"]
    conv = conv_file.parse((storage.read("users", f"{base}/conversation.md") or b"").decode())
    out = capfd.readouterr().out
    lines_log = [line for line in out.splitlines() if '"llm_call"' in line]
    log = [json.loads(line) for line in lines_log]
    model_usd, search_usd, queries = _price(log)
    steps = [line for line in answer.split("\n") if line.startswith("- ")]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    before_sources = answer.split("\n\nДжерела:")[0].rstrip()
    lines = ["# Live tracer research-deep (task 303, S3, AC3)", "", f"Run: {stamp}", ""]
    lines += [
        f"answered: {isinstance(events[-1], Answered)}; рішення роутера (останнє): {routing[-1]['kind']}",
        "",
    ]
    lines += ["## Відповідь (як показано)", "", answer, ""]
    for entry in research:
        lines += [f"## research.json: {entry['depth']} (turn {entry['turn']})", ""]
        lines += [f"- question: {entry['question']}", f"- запити: {entry['queries']}"]
        lines += [f"- джерела: {[s['url'] for s in entry['sources']]}", ""]
    lines += ["## Час і ціна", "", f"- загальний час відповіді: {total_s:.1f} с"]
    lines += [
        f"- викликів моделі: {len(log)}; пошукових запитів: {queries}; підпитань у кроках: {len(steps)}"
    ]
    lines += [f"- ціна: модель ${model_usd:.3f}; пошук ${search_usd:.3f} понад 5 000 безплатних ($0 до них)"]
    lines += [
        f"- разом ${model_usd + search_usd:.3f} (з пошуком) / ${model_usd:.3f} (у межах безплатних)",
        "",
    ]
    lines += [f"- закінчується питанням: {before_sources.endswith('?')}"]
    lines += [f"- пункти fact: {[i['text'] for i in problem_map.get('items', []) if i['type'] == 'fact']}"]
    last = conv.sessions[-1].turns[-1]
    lines += [f"- conversation.md = показане: {last.text == conv_file.normalize(answer)}", ""]
    lines += ["## Рядки `llm_call`", "", "```", *lines_log, "```", ""]
    path = SPIKES / f"research-deep-live-{stamp}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(out, end="")
    print(path)
    assert isinstance(events[-1], Answered), events[-1]
    assert len(steps) >= 2 and "\n\nДжерела: [" in answer, answer
    assert deep and deep[0]["question"] and deep[0]["report"] and deep[0]["queries"] and deep[0]["sources"], (
        research
    )
    assert log and all("latency_ms" in c and "prompt_tokens" in c for c in log), log
