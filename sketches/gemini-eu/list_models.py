"""List Gemini publisher models Vertex AI reports (catalogue, not regional availability)."""
import sys
from common import session

loc = sys.argv[1] if len(sys.argv) > 1 else "europe-west3"
url = f"https://europe-west3-aiplatform.googleapis.com/v1beta1/publishers/google/models?pageSize=200&listAllVersions=true"
names, token = [], None
while True:
    r = session().get(url + (f"&pageToken={token}" if token else ""), headers={"x-goog-user-project": "pocket-lawyer-431614"})
    print("HTTP", r.status_code) if r.status_code != 200 else None
    j = r.json()
    for m in j.get("publisherModels", []):
        n = m["name"].split("/")[-1]
        if "gemini" in n and "pro" in n:
            names.append(f'{n}  stage={m.get("launchStage")}  ver={m.get("versionId")}')
    token = j.get("nextPageToken")
    if not token:
        break
print("\n".join(sorted(set(names))) or j)
