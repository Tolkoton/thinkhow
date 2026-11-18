"""Spike (task 314, critic back-edge): the Max agent's own plan, a change to it,
a start (cancelled at once), and
what `get` raises for an unknown id."""

import json
import sys
import time
from typing import Any

from google import genai

MAX = "deep-research-max-preview-04-2026"
c = genai.Client()


def done(iid: str) -> Any:
    while True:
        got = c.interactions.get(id=iid)
        if got.status != "in_progress":
            return got
        time.sleep(3)


brief = open(sys.argv[1], encoding="utf-8").read()
t0 = time.time()
cfg: Any = {"type": "deep-research", "collaborative_planning": True, "visualization": "off"}
first: Any = c.interactions.create(agent=MAX, input=brief, agent_config=cfg, background=True, store=True)
plan = done(first.id)
print(
    "1 max plan",
    plan.status,
    round(time.time() - t0, 1),
    "s, marker:",
    "**Research Plan:**" in (plan.output_text or ""),
)
print(plan.output_text)
t0 = time.time()
made: Any = c.interactions.create(
    agent=MAX,
    input="Додай ще порівняння з Києвом.",
    previous_interaction_id=plan.id,
    agent_config=cfg,
    background=True,
    store=True,
)
change = done(made.id)
print(
    "2 max change",
    change.status,
    round(time.time() - t0, 1),
    "s, marker:",
    "**Research Plan:**" in (change.output_text or ""),
)
start_cfg: Any = {"type": "deep-research", "collaborative_planning": False, "visualization": "off"}
started: Any = c.interactions.create(
    agent=MAX,
    input="The plan is approved. Start the research; write the report in the language named in the request.",
    previous_interaction_id=change.id,
    agent_config=start_cfg,
    background=True,
    store=True,
)
time.sleep(15)
print("3 max start", c.interactions.get(id=started.id).status)
c.interactions.cancel(id=started.id)
time.sleep(5)
after = c.interactions.get(id=started.id)
print(
    "3 after cancel",
    after.status,
    json.dumps(json.loads(after.model_dump_json()).get("usage"), ensure_ascii=False),
)
for bogus in ("v1_bogus", "v1_" + plan.id[3:-4] + "AAAA"):
    try:
        c.interactions.get(id=bogus)
        print("4", bogus, "no exception")
    except Exception as exc:  # noqa: BLE001 — the spike records whatever comes
        print(
            "4",
            bogus,
            type(exc).__module__,
            type(exc).__name__,
            "status_code",
            getattr(exc, "status_code", None),
            "code",
            getattr(exc, "code", None),
            str(exc)[:200],
        )
