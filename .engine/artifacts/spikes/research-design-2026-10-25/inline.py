"""Spike 303: the facilitator's own streamed JSON call with a web-search tool: does it search where it should, how slow."""
import re, sys, time
from pathlib import Path
import yaml
from google import genai
from google.genai import types
from thinkhow.knowledge import Card
from thinkhow.facilitation.respond import system_instruction, answer_schema

SECTION = """# Факти про світ
У тебе є пошук в інтернеті. Якщо людина питає факт про світ або каже, що не знає того, що можна дізнатися з інтернету
(ціни, ринок, як зазвичай роблять інші, де клієнти шукають виконавців, правила, статистика), — не питай її про це:
знайди сам і коротко дай знайдене у reply, а тоді — одне питання, щоб вона думала далі з цими фактами. Рішення й
вибір лишаються за людиною. Не шукай фактів про саму людину — про це питай її."""

def turns(path, upto):
    txt = open(path, encoding="utf-8").read()
    parts = re.split(r"<!-- thinkhow:turn (\d+) (user|model) \S+ -->\n", txt)[1:]
    return [(int(parts[i]), parts[i+1], parts[i+2].strip()) for i in range(0, len(parts), 3) if int(parts[i]) <= upto]

card = Card.model_validate(yaml.safe_load(Path("cards/weighted-matrix.yaml").read_text(encoding="utf-8")))
tool = sys.argv[2]
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
system = system_instruction(card, [], "українська (uk)", True) + ("\n" + SECTION if tool != "none" else "")
tools = {"wge": [types.Tool(enterprise_web_search=types.EnterpriseWebSearch())],
         "gs": [types.Tool(google_search=types.GoogleSearch())], "none": None}[tool]
for upto in [17, 19, 21, 25]:
    ts = turns(sys.argv[1], upto)
    contents = [types.Content(role=r, parts=[types.Part(text=t)]) for _, r, t in ts[:-1]]
    contents.append(types.Content(role="user", parts=[types.Part(text=f"[Репліка людини #{upto}]\n{ts[-1][2]}")]))
    t0 = time.time(); first = None; chunks = []; gm = None
    for ch in c.models.generate_content_stream(model="gemini-4-argon", contents=contents, config=types.GenerateContentConfig(
            system_instruction=system, tools=tools, response_mime_type="application/json",
            response_json_schema=answer_schema(card).model_json_schema())):
        for cand in ch.candidates or []:
            if cand.grounding_metadata and (cand.grounding_metadata.grounding_chunks or cand.grounding_metadata.web_search_queries): gm = cand.grounding_metadata
            for p in (cand.content.parts if cand.content else None) or []:
                if p.text and not p.thought:
                    first = first or time.time() - t0; chunks.append(p.text)
    raw = "".join(chunks)
    reply = answer_schema(card).model_validate_json(raw).reply
    q = gm.web_search_queries if gm else None; n = len(gm.grounding_chunks or []) if gm else 0
    print(f"{tool} #{upto} first {first:.1f}s total {time.time()-t0:.1f}s queries {q} sources {n}\n  {reply}\n", flush=True)
