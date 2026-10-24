import time, json, concurrent.futures as cf
from google import genai
from google.genai import types
from pydantic import BaseModel
class Plan(BaseModel):
    questions: list[str]
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
M="gemini-4-argon"
Q="Скільки зараз коштує оренда однокімнатної квартири у Львові і як змінилися ціни за останній рік?"
t0=time.time(); usage=[]
p=c.models.generate_content(model=M, contents=f"Розклади питання на 4 підпитання для пошуку в інтернеті:\n{Q}", config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=Plan.model_json_schema()))
plan=Plan.model_validate_json(p.text); usage.append(p.usage_metadata)
print("plan", round(time.time()-t0,1), plan.questions)
def one(q):
    t=time.time()
    r=c.models.generate_content(model=M, contents=f"Знайди факти з джерелами: {q}", config=types.GenerateContentConfig(tools=[types.Tool(enterprise_web_search=types.EnterpriseWebSearch())]))
    gm=r.candidates[0].grounding_metadata
    srcs=[(ch.web.title, ch.web.uri[:60]) for ch in (gm.grounding_chunks or [])] if gm else []
    return q, r.text, srcs, round(time.time()-t,1), r.usage_metadata, len(gm.web_search_queries or []) if gm else 0
with cf.ThreadPoolExecutor(4) as ex: res=list(ex.map(one, plan.questions))
for q,txt,s,dt,u,nq in res: print("sub", dt, nq, len(s), q[:60]); usage.append(u)
notes="\n\n".join(f"## {q}\n{txt}\nДжерела: {s}" for q,txt,s,_,_,_ in res)
t=time.time()
f=c.models.generate_content(model=M, contents=f"Склади стислий звіт з джерелами на питання: {Q}\n\nЗнахідки:\n{notes}")
usage.append(f.usage_metadata)
print("synth", round(time.time()-t,1)); print("total", round(time.time()-t0,1))
print(f.text[:2500])
pt=sum(u.prompt_token_count or 0 for u in usage); ot=sum((u.candidates_token_count or 0)+(u.thoughts_token_count or 0) for u in usage)
print("tokens in/out", pt, ot, "grounded queries", sum(r[5] for r in res))
