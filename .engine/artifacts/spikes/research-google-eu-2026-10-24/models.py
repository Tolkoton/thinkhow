from google import genai
for loc in ["eu","europe-west4","global"]:
    c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location=loc)
    try:
        names=[m.name for m in c.models.list()]
        print(loc, len(names), [n for n in names if "research" in n or "deep" in n][:20])
    except Exception as e: print(loc,"ERR",str(e)[:300])
