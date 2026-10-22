"""Who is asking: the signed IAP header, or a fixed person in local mode (M2 S4, M3 A2).

Does NOT decide who is the owner (that is access) and never reads identity from a URL or a form.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from thinkhow.platform.config import Settings

IAP_HEADER = "x-goog-iap-jwt-assertion"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


@dataclass(frozen=True)
class Identity:
    id: str
    email: str


class IdentityError(Exception):
    """The request carries no verifiable identity."""


class IapIdentity:
    def __init__(self, audience: str, verify: Callable[[str, str], Mapping[str, object]]) -> None:
        self.audience = audience
        self.verify = verify

    def identify(self, headers: Mapping[str, str]) -> Identity:
        """Flow: find the header → verify the signature → read the person from the claims."""
        token = _iap_token(headers)
        try:
            claims = self.verify(token, self.audience)
        except Exception as exc:
            raise IdentityError("the IAP assertion does not verify") from exc
        return _identity_from_claims(claims)


def _iap_token(headers: Mapping[str, str]) -> str:
    for name, value in headers.items():
        if name.lower() == IAP_HEADER and value:
            return value
    raise IdentityError("no IAP assertion header")


def _identity_from_claims(claims: Mapping[str, object]) -> Identity:
    sub, email = claims.get("sub"), claims.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or not email:
        raise IdentityError("the IAP assertion has no sub or email")
    person_id = sub.rsplit(":", 1)[-1]
    if not SAFE_ID.fullmatch(person_id):
        raise IdentityError("the IAP subject is not a safe id")
    return Identity(id=person_id, email=email)


class FixedIdentity:
    def __init__(self, identity: Identity) -> None:
        self.identity = identity

    def identify(self, headers: Mapping[str, str]) -> Identity:
        return self.identity


def make_identity(settings: Settings) -> IapIdentity | FixedIdentity:
    if settings.local:
        return FixedIdentity(Identity(id=settings.local_user_id, email=settings.local_user_email))
    return IapIdentity(settings.iap_audience, _verify_with_google)


def _verify_with_google(token: str, audience: str) -> Mapping[str, object]:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    claims: Mapping[str, object] = id_token.verify_token(
        token, google_requests.Request(), audience=audience, certs_url=IAP_CERTS_URL
    )
    return claims
