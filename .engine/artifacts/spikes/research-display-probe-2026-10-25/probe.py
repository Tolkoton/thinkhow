"""Probe for research-display Q4: the full search_entry_point.rendered_content of WGE on Vertex eu — anchors, targets, scripts."""
import re
import sys
from google import genai
from google.genai import types

c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location="eu")
r = c.models.generate_content(
    model="gemini-4-argon",
    contents="Скільки зараз коштує новий Škoda Octavia Combi у Німеччині? Коротко.",
    config=types.GenerateContentConfig(tools=[types.Tool(enterprise_web_search=types.EnterpriseWebSearch())]),
)
html = r.candidates[0].grounding_metadata.search_entry_point.rendered_content
open(sys.argv[1], "w", encoding="utf-8").write(html)
print("length", len(html))
print("anchors", len(re.findall(r"<a\b", html)))
print("target attrs", re.findall(r"target=\"?[^\s\">]*", html)[:5])
print("<base", "<base" in html, "<script", "<script" in html, "onclick", "onclick" in html)
print("first anchor", (re.findall(r"<a\b[^>]*>", html) or ["-"])[0][:300])
