"""Which TTS-capable Google models the project sees, per Vertex location (read-only listing)."""
import sys
from google import genai
for loc in sys.argv[1:]:
    c = genai.Client(vertexai=True, project="pocket-lawyer-431614", location=loc)
    try:
        names = [m.name for m in c.models.list() if any(k in (m.name or "") for k in ("tts", "audio", "live", "native"))]
        print(loc, names)
    except Exception as e:
        print(loc, "ERR", type(e).__name__, str(e)[:200])
