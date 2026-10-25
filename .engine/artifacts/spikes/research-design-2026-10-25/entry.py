"""Spike 303: what a grounded answer carries besides text — search_entry_point, chunk URIs, supports; redirect resolution."""
import time, urllib.request, urllib.error
from google import genai
from google.genai import types
c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
for name, tool in [("wge", types.Tool(enterprise_web_search=types.EnterpriseWebSearch())), ("gs", types.Tool(google_search=types.GoogleSearch()))]:
    t = time.time()
    r = c.models.generate_content(model="gemini-4-argon", contents="Скільки коштує Skoda Octavia Combi в Німеччині?",
        config=types.GenerateContentConfig(tools=[tool]))
    gm = r.candidates[0].grounding_metadata
    sep = gm.search_entry_point
    print(name, round(time.time()-t, 1), "queries", gm.web_search_queries)
    print("  entry_point:", None if sep is None else (len(sep.rendered_content or ""), (sep.rendered_content or "")[:300].replace("\n", " ")))
    print("  supports:", len(gm.grounding_supports or []))
    for ch in (gm.grounding_chunks or [])[:3]:
        print("  chunk:", ch.web.title, ch.web.domain if hasattr(ch.web, "domain") else "", ch.web.uri[:90])
        req = urllib.request.Request(ch.web.uri, method="HEAD")
        class NoRedir(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        try:
            urllib.request.build_opener(NoRedir).open(req, timeout=10)
            print("   no redirect")
        except urllib.error.HTTPError as e:
            print("   ", e.code, e.headers.get("Location", "")[:120])
