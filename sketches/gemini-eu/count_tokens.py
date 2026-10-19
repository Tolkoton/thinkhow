"""Count tokens of each context file with the model under test (countTokens on eu)."""
import sys
from common import model_url, session

for path in sys.argv[1:]:
    text = open(path).read()
    r = session().post(model_url("eu", "gemini-4-argon", "countTokens"),
                       json={"contents": [{"role": "user", "parts": [{"text": text}]}]}, timeout=60)
    print(path, r.status_code, r.json().get("totalTokens", r.text[:200]))
