"""Spike (task 314): Max started fresh with the approved plan in its input (no previous interaction) —
accepted and
running? Cancelled at once. And what `get` raises for an unknown id."""

import json
import sys
import time
from typing import Any

from google import genai

c = genai.Client()
plan = json.load(open(sys.argv[1]))["output_text"].split("**Research Plan:**")[-1].strip()
brief = open(sys.argv[2], encoding="utf-8").read()
text = f"{brief}\n\n[Approved research plan]\n{plan}\n\nThe plan is approved. Run the research by it."
cfg: Any = {"type": "deep-research", "collaborative_planning": False, "visualization": "off"}
made: Any = c.interactions.create(
    agent="deep-research-max-preview-04-2026", input=text, agent_config=cfg, background=True, store=True
)
time.sleep(15)
print("max fresh start:", c.interactions.get(id=made.id).status)
c.interactions.cancel(id=made.id)
time.sleep(5)
got = c.interactions.get(id=made.id)
print(
    "after cancel:",
    got.status,
    json.dumps(json.loads(got.model_dump_json()).get("usage"), ensure_ascii=False),
)
for bogus in ("v1_bogus", made.id[:-6] + "AAAAAA"):
    try:
        c.interactions.get(id=bogus)
        print("unknown id", bogus, "no exception")
    except Exception as exc:  # noqa: BLE001 — the spike records whatever comes
        print(
            "unknown id",
            bogus,
            type(exc).__module__,
            type(exc).__name__,
            "status_code",
            getattr(exc, "status_code", None),
            "code",
            getattr(exc, "code", None),
            str(exc)[:200],
        )
