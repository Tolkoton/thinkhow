import time
from google import genai
from google.genai import types
for loc in ["eu","europe-west4"]:
    c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location=loc)
    t=time.time()
    try:
        r=c.models.generate_content(model="gemini-4-argon", contents="Скільки коштує Skoda Octavia Combi в Німеччині? З джерелом.", config=types.GenerateContentConfig(tools=[types.Tool(enterprise_web_search=types.EnterpriseWebSearch())]))
        gm=r.candidates[0].grounding_metadata
        print(loc, "OK", round(time.time()-t,1), r.text[:300].replace("\n"," "), "| queries", gm.web_search_queries if gm else None, "| chunks", len(gm.grounding_chunks or []) if gm else 0)
    except Exception as e: print(loc,"ERR",type(e).__name__,str(e)[:400])
