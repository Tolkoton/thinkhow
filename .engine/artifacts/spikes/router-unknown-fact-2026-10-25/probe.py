"""Probe: does one more router rule make «answer» on the owner's «не знаю» turns #17, #19, #21 (and not on #25)?

Runs facilitation.route on the owner's real history (bucket, ADC) with the rule appended to ROUTER_RULES,
three times per turn, and prints the actions. The owner's text is not printed.
"""
import os, subprocess, sys
import importlib
r = importlib.import_module("thinkhow.facilitation.route")
from thinkhow.facilitation.types import FacilitationContext, ProblemMap, Turn
from thinkhow.knowledge import current, seed
from thinkhow.platform.config import load_settings
from thinkhow.platform.llm import make_llm
from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import conversation as conv_file
import tempfile, pathlib

RULE = sys.argv[1] if len(sys.argv) > 1 else ""
URI = "gs://pocket-lawyer-431614-thinkhow-users/104839836105981044615/t-d824f508a729/"
conv = conv_file.parse(subprocess.run(["gcloud", "storage", "cat", URI + "conversation.md"], capture_output=True, text=True, check=True).stdout)
pm = ProblemMap.model_validate_json(subprocess.run(["gcloud", "storage", "cat", URI + "map.json"], capture_output=True, text=True, check=True).stdout)
turns = [t for s in conv.sessions for t in s.turns]
st = LocalStorage(pathlib.Path(tempfile.mkdtemp())); seed(st, pathlib.Path("cards")); k = current(st)
env = {**os.environ, "THINKHOW_LOCAL": "false", "THINKHOW_USERS_BUCKET": "-", "THINKHOW_SYSTEM_BUCKET": "-", "THINKHOW_OWNER_EMAIL": "-"}
llm = make_llm(load_settings(env), lambda *_: "")
if RULE:
    r.ROUTER_RULES = r.ROUTER_RULES + "\n" + RULE
for no in (17, 19, 21, 25):
    hist = [Turn(t.role, t.text) for t in turns if t.no < no]
    items = [i for i in pm.items if int(i.turn[1:]) < no]
    ctx = FacilitationContext("pre-mortem", hist, ProblemMap(items=items, last_turn=no - 1), no, turns[no - 1].text, "Українська (uk-UA)", ())
    acts = [r.route(ctx, k, llm).action for _ in range(3)]
    print(f"#{no}: {acts}", flush=True)
