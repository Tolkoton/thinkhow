"""Shared Vertex AI REST access through Application Default Credentials (google-auth)."""
import google.auth
import google.auth.transport.requests

PROJECT = "pocket-lawyer-431614"
_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
_session = google.auth.transport.requests.AuthorizedSession(_creds)


def host(location):
    return "aiplatform.eu.rep.googleapis.com" if location == "eu" else f"{location}-aiplatform.googleapis.com"


def model_url(location, model, method, version="v1"):
    return (f"https://{host(location)}/{version}/projects/{PROJECT}/locations/{location}"
            f"/publishers/google/models/{model}:{method}")


def session():
    return _session
