"""Estimate the size of 18 router halves: count the router fields of the 3 full cards in the library."""
import re
import sys
import yaml
from common import model_url, session

ROUTER_KEYS = ["framework_id", "name_original", "purpose", "taxonomy_fit", "when_to_use_signals",
               "when_NOT_to_use_signals", "positive_examples", "negative_examples"]
lib = open(sys.argv[1]).read()
blocks = [b for b in re.findall(r"```yaml\n(.*?)```", lib, re.S) if b.startswith("framework_id:")]
counts = []
for b in blocks:
    card = yaml.safe_load(b)
    half = yaml.safe_dump({k: card[k] for k in ROUTER_KEYS if k in card}, allow_unicode=True, sort_keys=False)
    r = session().post(model_url("eu", "gemini-4-argon", "countTokens"),
                       json={"contents": [{"role": "user", "parts": [{"text": half}]}]}, timeout=60)
    counts.append(r.json()["totalTokens"])
    print(card["framework_id"], counts[-1])
print("mean", round(sum(counts) / len(counts)), "x18 =", round(18 * sum(counts) / len(counts)))
