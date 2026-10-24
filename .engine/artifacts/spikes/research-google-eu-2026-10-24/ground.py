import sys, time, json
from google import genai
from google.genai import types
loc = sys.argv[1]; model = sys.argv[2]; q = sys.argv[3]
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location=loc)
t=time.time()
try:
    r = c.models.generate_content(model=model, contents=q, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:600]); sys.exit()
dt=time.time()-t
print("latency", round(dt,1))
print(r.text[:1500])
gm = r.candidates[0].grounding_metadata
if gm:
    print("queries", gm.web_search_queries)
    for ch in (gm.grounding_chunks or [])[:8]:
        print(" src", ch.web.title if ch.web else ch)
print("usage", r.usage_metadata)
