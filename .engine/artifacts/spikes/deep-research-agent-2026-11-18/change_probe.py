"""Spike (task 314): a change to the agent's plan by previous_interaction_id + collaborative_planning=true;
and visualization="off" accepted."""

import json
import sys
import time

from google import genai

c = genai.Client()
prev = json.load(open(sys.argv[1]))["id"]
t0 = time.time()
made = c.interactions.create(
    agent="deep-research-preview-04-2026",
    input=sys.argv[2],
    previous_interaction_id=prev,
    agent_config={"type": "deep-research", "collaborative_planning": True, "visualization": "off"},
    background=True,
    store=True,
)
while True:
    got = c.interactions.get(id=made.id)
    if got.status != "in_progress":
        break
    time.sleep(3)
d = json.loads(got.model_dump_json())
d["_elapsed_s"] = round(time.time() - t0, 1)
json.dump(d, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
print(d["status"], d["_elapsed_s"], "id", d["id"])
print(d.get("output_text"))
