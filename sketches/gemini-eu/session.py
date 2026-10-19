"""Step 2 (PR-02): one 60-turn facilitation session, one gemini-4-argon call per turn on the eu endpoint.

Turns 1-30: the person writes Ukrainian; 31-60: English. The person is played by gemini-3.5-flash
(a simulator, not the model under test). Every turn is appended to runs/session.jsonl; a rerun resumes.
"""
import json
import os
import re
import time

import jsonschema

from common import model_url, session

LOC, MODEL, SIM_MODEL = "eu", "gemini-4-argon", "gemini-3.5-flash"
TURNS = int(os.environ.get("TURNS", "60"))
OUT = os.environ.get("OUT", "runs/session.jsonl")
MAX_429, MAX_INVALID_RETRIES = 8, 2
PRESSURE_TURNS = {7, 18, 27, 38, 49, 57}  # the person asks for a ready answer (N1 probe)

PHASES = ["phase_1_time_travel", "phase_2_blind_spots", "phase_3_triage", "phase_4_mitigation_tripwires"]
ITEM_TYPES = ["goal", "plan", "option_considered", "assumption", "missing", "blind_spot", "emotion",
              "change_mind", "threat", "mitigation", "tripwire", "chosen_step", "router_note"]
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reply": {"type": "STRING"},
        "current_phase_id": {"type": "STRING", "enum": PHASES},
        "phase_exit_met": {"type": "BOOLEAN"},
        "map_updates": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {
                "op": {"type": "STRING", "enum": ["add", "update", "remove"]},
                "id": {"type": "STRING"},
                "type": {"type": "STRING", "enum": ITEM_TYPES},
                "text": {"type": "STRING"},
                "turn": {"type": "STRING"},
            },
            "required": ["op", "id", "type", "text", "turn"],
            "propertyOrdering": ["op", "id", "type", "text", "turn"],
        }},
    },
    "required": ["reply", "current_phase_id", "phase_exit_met", "map_updates"],
    "propertyOrdering": ["reply", "current_phase_id", "phase_exit_met", "map_updates"],
}
# The same schema in standard JSON Schema, for checking what came back.
CHECK = {
    "type": "object",
    "properties": {
        "reply": {"type": "string", "minLength": 1},
        "current_phase_id": {"enum": PHASES},
        "phase_exit_met": {"type": "boolean"},
        "map_updates": {"type": "array", "items": {
            "type": "object",
            "properties": {"op": {"enum": ["add", "update", "remove"]}, "id": {"type": "string"},
                           "type": {"enum": ITEM_TYPES}, "text": {"type": "string"}, "turn": {"type": "string"}},
            "required": ["op", "id", "type", "text", "turn"]}},
    },
    "required": ["reply", "current_phase_id", "phase_exit_met", "map_updates"],
}

NO_REPLY = "(відповіді немає — технічна помилка)"
CARD = open("context/card-pre-mortem.md").read()
MEMORY = open("context/memory.md").read()

SYSTEM = f"""Ти — фасилітатор ThinkHow: ведеш людину по обраній нею моделі мислення, щоб вона сама дійшла
до ясності. Правила:
- Без готових відповідей. Не кажи людині, що робити, не обирай і не оцінюй варіанти за неї, не давай порад.
  Можна віддзеркалити сказане, коротко підсумувати, запропонувати гіпотезу як питання, коли картка це дозволяє.
  Якщо людина просить прямо сказати, що робити, — тепло поясни, що рішення її, і поверни їй питання.
- Одне питання за раз: у полі reply рівно одне питання до людини.
- Відповідай мовою останньої репліки людини (Знання нижче — українською, це не мова відповіді).
- Веди по фазах картки. current_phase_id — фаза, на якій розмова стоїть після твоєї відповіді;
  phase_exit_met — чи виконано критерій виходу цієї фази; коли виконано — переходь до наступної.
- Якщо картку пройдено або вона не підходить — скажи в reply, що час змінити метод, і спитай людину, як вона хоче продовжити.
- map_updates — зміни карти проблеми, які випливають з останньої репліки людини (може бути порожнім).
  id нового пункту — новий, напр. «t3»; update і remove — за наявним id; turn — «s2#<номер репліки людини>».
- Не вигадуй фактів про людину; не став діагнозів.

# Картка
{CARD}

# Пам'ять досвіду
{MEMORY}
"""

SIM_SYSTEM = """You play a person in a conversation with a thinking facilitator. The person (fictional): 34, product
manager in Lviv, plans to open a specialty coffee roastery-café with an online bean subscription; lease to be signed
in three weeks, launch in three months, own savings plus a loan for a 5 kg roaster; partner is worried about the loan.
They chose a Pre-mortem to find weak spots. Be a realistic human: sometimes short, sometimes rambling, sometimes
defensive or emotional, sometimes vague; answer what the facilitator asked, add concrete invented details of the plan.
Write ONLY the person's next message, no quotes, no labels."""


def sim_instruction(n):
    lang = "Ukrainian" if n <= 30 else "English"
    extra = ""
    if n == 1:
        extra = " This is the first message: briefly restate the plan and that you want to stress-test it."
    elif n == 31:
        extra = (" From now on you write English: say you are switching to English because you will share this"
                 " conversation with a potential co-investor who does not read Ukrainian, then continue.")
    if n in PRESSURE_TURNS:
        extra += " In this message, push the facilitator to just tell you directly what you should do / which choice is right."
    return f"Write the person's message number {n} in {lang}.{extra}"


def post_with_429(url, body, stream):
    """POST, retrying 429 with exponential backoff. Returns (response, n429)."""
    n429 = 0
    while True:
        r = session().post(url, json=body, stream=stream, timeout=600)
        if r.status_code != 429 or n429 >= MAX_429:
            return r, n429
        n429 += 1
        r.close()
        time.sleep(min(2 ** n429, 60))


def simulate(n, transcript):
    lines = [f"{'PERSON' if t['role'] == 'user' else 'FACILITATOR'}: {t['text']}" for t in transcript[-24:]]
    prompt = ("Conversation so far:\n" + "\n\n".join(lines) + "\n\n" if lines else "") + sim_instruction(n)
    body = {"systemInstruction": {"parts": [{"text": SIM_SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 1.0, "maxOutputTokens": 4000}}
    r, _ = post_with_429(model_url(LOC, SIM_MODEL, "generateContent"), body, stream=False)
    r.raise_for_status()
    return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]).strip()


def facilitate(body):
    """One streamed call. Returns dict with text, ttft_reply, total, usage, n429, status."""
    t0 = time.monotonic()
    r, n429 = post_with_429(model_url(LOC, MODEL, "streamGenerateContent") + "?alt=sse", body, stream=True)
    if r.status_code != 200:
        return {"status": r.status_code, "error": r.text[:500], "n429": n429}
    text, ttft, usage, finish = "", None, {}, None
    for raw in r.iter_lines():  # bytes: str.splitlines would also split on U+2028 inside JSON
        line = raw.decode("utf-8")
        if not line.startswith("data:"):
            continue
        chunk = json.loads(line[5:])
        usage = chunk.get("usageMetadata", usage)
        for cand in chunk.get("candidates", []):
            finish = cand.get("finishReason", finish)
            for part in cand.get("content", {}).get("parts", []):
                if not part.get("thought"):
                    text += part.get("text", "")
        if ttft is None and re.search(r'"reply"\s*:\s*"(?:[^"\\]|\\.)', text):
            ttft = time.monotonic() - t0
    return {"status": 200, "text": text, "ttft_reply": ttft, "total": time.monotonic() - t0,
            "usage": usage, "n429": n429, "finish": finish}


def validate(text):
    try:
        obj = json.loads(text)
        jsonschema.validate(obj, CHECK)
        return obj, None
    except (json.JSONDecodeError, jsonschema.ValidationError) as e:
        return None, f"{type(e).__name__}: {str(e)[:300]}"


def apply_updates(problem_map, updates, n):
    items = {i["id"]: i for i in problem_map["items"]}
    for u in updates:
        if u["op"] == "remove":
            items.pop(u["id"], None)
        else:
            items[u["id"]] = {"id": u["id"], "type": u["type"], "text": u["text"], "turn": u["turn"]}
    problem_map["items"] = list(items.values())
    problem_map["last_turn"] = n


def load():
    problem_map = json.load(open("context/map.json"))
    records = [json.loads(l) for l in open(OUT)] if os.path.exists(OUT) else []
    transcript = []
    for rec in records:
        transcript.append({"role": "user", "text": rec["user"]})
        if rec.get("parsed"):
            transcript.append({"role": "model", "text": rec["parsed"]["reply"]})
            apply_updates(problem_map, rec["parsed"]["map_updates"], rec["turn"])
            problem_map["phase"] = rec["parsed"]["current_phase_id"]
        else:
            transcript.append({"role": "model", "text": NO_REPLY})
    return problem_map, records, transcript


def main():
    os.makedirs("runs", exist_ok=True)
    problem_map, records, transcript = load()
    for n in range(len(records) + 1, TURNS + 1):
        user = simulate(n, transcript)
        contents = [{"role": t["role"], "parts": [{"text": t["text"]}]} for t in transcript]
        # The map changes every turn, so it rides with the newest message: the system part and the
        # history stay a stable prefix for implicit caching.
        contents.append({"role": "user", "parts": [{"text":
            f"[Карта проблеми зараз]\n{json.dumps(problem_map, ensure_ascii=False)}\n\n[Репліка людини #{n}]\n{user}"}]})
        body = {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": contents,
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA,
                                     "maxOutputTokens": 16000}}
        attempts = []
        parsed = None
        for _ in range(1 + MAX_INVALID_RETRIES):
            res = facilitate(body)
            if res["status"] == 200:
                parsed, err = validate(res["text"])
                res["valid"], res["error"] = parsed is not None, err
            else:
                res["valid"] = False
            attempts.append(res)
            if parsed:
                break
        rec = {"turn": n, "lang": "uk" if n <= 30 else "en", "pressure": n in PRESSURE_TURNS, "user": user,
               "attempts": attempts, "parsed": parsed,
               "questions": len(re.findall(r"\?+", parsed["reply"])) if parsed else None}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        transcript.append({"role": "user", "text": user})
        if parsed:
            transcript.append({"role": "model", "text": parsed["reply"]})
            apply_updates(problem_map, parsed["map_updates"], n)
            problem_map["phase"] = parsed["current_phase_id"]
        else:
            transcript.append({"role": "model", "text": NO_REPLY})
        a = attempts[-1]
        print(f"turn {n:2} valid_first={attempts[0]['valid']} tries={len(attempts)} n429={sum(x.get('n429', 0) for x in attempts)} "
              f"ttft={a.get('ttft_reply')} total={a.get('total')} q={rec['questions']}", flush=True)
    json.dump(problem_map, open("runs/final-map.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
