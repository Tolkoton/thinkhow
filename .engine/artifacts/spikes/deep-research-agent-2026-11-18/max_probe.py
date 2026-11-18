"""Spike (task 314): does the Max agent take a plan made by the standard agent? Started, then cancelled."""

import json
import sys
import time

from google import genai

c = genai.Client()
prev = json.load(open(sys.argv[1]))["id"]
made = c.interactions.create(
    agent="deep-research-max-preview-04-2026",
    input="Так, запускай.",
    previous_interaction_id=prev,
    agent_config={"type": "deep-research", "collaborative_planning": False},
    background=True,
    store=True,
)
print("created", made.id, made.status)
time.sleep(20)
got = c.interactions.get(id=made.id)
print("after 20s", got.status, getattr(got, "errors", None))
c.interactions.cancel(id=made.id)
time.sleep(5)
got = c.interactions.get(id=made.id)
usage = json.loads(got.model_dump_json()).get("usage")
print("after cancel", got.status, json.dumps(usage, ensure_ascii=False))
