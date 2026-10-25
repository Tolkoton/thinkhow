"""Spike 303: how fast and how right is a classifier of the person's 'не знаю' (flash vs argon on eu)."""
import re, sys, time
from typing import Literal
from google import genai
from google.genai import types
from pydantic import BaseModel

class Need(BaseModel):
    kind: Literal["none", "world_fact", "reality_test"]
    question: str | None
    depth: Literal["quick", "deep"] | None
    why: str

SYSTEM = """Ти — частина ThinkHow, що вирішує, чи треба системі шукати факти про світ. Подивись на останню репліку людини
в контексті розмови. kind:
- "world_fact" — людина питає факт про світ або каже, що не знає того, що можна дізнатися з інтернету (ціни, ринок,
  як зазвичай роблять інші, де шукають клієнтів, правила, статистика). question — що саме шукати, одним реченням,
  мовою людини, з деталями її ситуації, що потрібні для пошуку. depth: "quick" — відповідь — один-два факти;
  "deep" — питання багатогранне (ринок, порівняння кількох шляхів), потребує кількох пошуків.
- "reality_test" — відповідь покаже лише реальність (чи відгукнуться клієнти, чи сподобається), її не знайти в інтернеті.
- "none" — решта: людина розповідає про себе, відповідає на питання, обирає; або не знає факту про саму себе.
"""
def turns(path, upto):
    txt = open(path, encoding="utf-8").read()
    parts = re.split(r"<!-- thinkhow:turn (\d+) (user|model) \S+ -->\n", txt)[1:]
    out = []
    for i in range(0, len(parts), 3):
        no, role, text = int(parts[i]), parts[i+1], parts[i+2].strip()
        if no <= upto: out.append((no, role, text))
    return out
conv = sys.argv[1]
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
for model in ["gemini-3.5-flash", "gemini-4-argon"]:
    for upto in [17, 19, 21, 23, 25, 29]:
        ts = turns(conv, upto)
        contents = [types.Content(role=r, parts=[types.Part(text=f"#{n}: {t}")]) for n, r, t in ts]
        t0 = time.time()
        r = c.models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(
            system_instruction=SYSTEM, response_mime_type="application/json", response_json_schema=Need.model_json_schema()))
        n = Need.model_validate_json(r.text)
        print(f"{model} #{upto} {time.time()-t0:.1f}s {n.kind} {n.depth} | {n.question} | {n.why[:120]}", flush=True)
