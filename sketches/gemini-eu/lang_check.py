"""Per reply: language by script (Cyrillic vs Latin letters), and whether it says «час змінити метод» / «change the method»."""
import json
import re

recs = [json.loads(l) for l in open("runs/session.jsonl")]
mismatch, change, two_q = [], [], []
for r in recs:
    rep = r["parsed"]["reply"]
    lang = "uk" if len(re.findall("[а-яіїєґА-ЯІЇЄҐ]", rep)) > len(re.findall("[a-zA-Z]", rep)) else "en"
    if lang != r["lang"]:
        mismatch.append(r["turn"])
    if re.search(r"змін\w* метод|change (the )?method", rep, re.I):
        change.append(r["turn"])
    if r["questions"] != 1:
        two_q.append(r["turn"])
print("reply language differs from the person's turn language:", mismatch or "none")
print(f"replies saying 'time to change method': {len(change)}, turns {change}")
print("replies with a question count other than 1:", two_q)
