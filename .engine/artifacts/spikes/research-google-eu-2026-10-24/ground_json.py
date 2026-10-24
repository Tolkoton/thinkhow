import sys, time, json
from google import genai
from google.genai import types
from pydantic import BaseModel
class Out(BaseModel):
    reply: str
    searched: bool
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
t=time.time()
try:
    r = c.models.generate_content(model="gemini-4-argon", contents="Скільки коштує Skoda Octavia Combi в Німеччині? Відповідай з джерелом.", config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], response_mime_type="application/json", response_json_schema=Out.model_json_schema()))
    print(round(time.time()-t,1), r.text[:800])
    gm=r.candidates[0].grounding_metadata
    print("gm", bool(gm), gm.web_search_queries if gm else None, len(gm.grounding_chunks or []) if gm else 0)
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:800])
