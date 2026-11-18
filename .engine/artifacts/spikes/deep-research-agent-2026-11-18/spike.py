"""Spike (task 314): the real Gemini Deep Research agent — the route, the plan, the time, the usage.

usage: spike.py plan <out.json> <question-file> [--vertex] [--max]
       spike.py go <out.json> <previous_interaction_id> <answer> [--vertex]
       spike.py get <out.json> <interaction_id> [--vertex]
"""

import json
import sys
import time
from typing import Any

from google import genai

AGENT = "deep-research-preview-04-2026"
AGENT_MAX = "deep-research-max-preview-04-2026"


def client(vertex: bool) -> genai.Client:
    if vertex:
        return genai.Client(vertexai=True, project="pocket-lawyer-431614", location="global")
    return genai.Client()


def wait(c: genai.Client, iid: str, t0: float) -> dict[str, Any]:
    while True:
        got = c.interactions.get(id=iid)
        status = getattr(got, "status", None)
        print(f"{time.time() - t0:7.1f}s status={status}", flush=True)
        if status not in ("in_progress", "queued", "running", None):
            result: dict[str, Any] = json.loads(got.model_dump_json())
            return result
        time.sleep(10)


def main() -> None:
    cmd, out = sys.argv[1], sys.argv[2]
    vertex = "--vertex" in sys.argv
    c = client(vertex)
    t0 = time.time()
    made: Any
    if cmd == "plan":
        question = open(sys.argv[3], encoding="utf-8").read()
        agent = AGENT_MAX if "--max" in sys.argv else AGENT
        made = c.interactions.create(
            agent=agent,
            input=question,
            agent_config={"type": "deep-research", "collaborative_planning": True},
            background=True,
            store=True,
        )
    elif cmd == "go":
        made = c.interactions.create(
            agent=AGENT,
            input=sys.argv[4],
            previous_interaction_id=sys.argv[3],
            agent_config={"type": "deep-research", "collaborative_planning": False},
            background=True,
            store=True,
        )
    else:
        made = c.interactions.get(id=sys.argv[3])
    print("id", made.id, flush=True)
    result = wait(c, made.id, t0)
    result["_elapsed_s"] = round(time.time() - t0, 1)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("elapsed", result["_elapsed_s"], "usage", json.dumps(result.get("usage"), ensure_ascii=False))


main()
