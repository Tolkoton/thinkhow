"""Contract tests of skel-platform: identity.py (slice tester; written from the contract, not the code)."""

from collections.abc import Mapping

import pytest

from thinkhow.platform.config import Settings
from thinkhow.platform.identity import FixedIdentity, IapIdentity, Identity, IdentityError, make_identity

AUD = "/projects/123/global/backendServices/456"


class Verify:
    def __init__(self, claims: Mapping[str, object] | Exception) -> None:
        self.claims = claims
        self.calls: list[tuple[str, str]] = []

    def __call__(self, token: str, audience: str) -> Mapping[str, object]:
        self.calls.append((token, audience))
        if isinstance(self.claims, Exception):
            raise self.claims
        return self.claims


def test_iap_identity_takes_id_after_last_colon_of_sub_and_email_claim() -> None:
    verify = Verify({"sub": "accounts.google.com:1234567890", "email": "ann@example.com"})
    who = IapIdentity(AUD, verify).identify({"x-goog-iap-jwt-assertion": "tok-1"})
    assert who == Identity(id="1234567890", email="ann@example.com")
    assert verify.calls == [("tok-1", AUD)]
    verify2 = Verify({"sub": "a:b:c:777", "email": "bob@example.com"})
    assert IapIdentity(AUD, verify2).identify({"x-goog-iap-jwt-assertion": "t"}).id == "777"


def test_iap_header_name_is_case_insensitive() -> None:
    verify = Verify({"sub": "accounts.google.com:42", "email": "ann@example.com"})
    for name in ("X-Goog-IAP-JWT-Assertion", "X-GOOG-IAP-JWT-ASSERTION"):
        assert IapIdentity(AUD, verify).identify({name: "tok"}) == Identity("42", "ann@example.com")


def test_iap_identity_refuses_what_cannot_be_verified() -> None:
    good = {"sub": "accounts.google.com:42", "email": "ann@example.com"}
    cases: list[tuple[Verify, dict[str, str]]] = [
        (Verify(good), {}),
        (Verify(good), {"authorization": "Bearer x"}),
        (Verify(ValueError("bad signature")), {"x-goog-iap-jwt-assertion": "tok"}),
        (Verify({"email": "ann@example.com"}), {"x-goog-iap-jwt-assertion": "tok"}),
        (Verify({"sub": "accounts.google.com:42"}), {"x-goog-iap-jwt-assertion": "tok"}),
    ]
    for verify, headers in cases:
        with pytest.raises(IdentityError):
            IapIdentity(AUD, verify).identify(headers)


def test_iap_id_must_match_the_safe_pattern() -> None:
    ok_128 = "a" * 128
    verify = Verify({"sub": f"accounts.google.com:{ok_128}", "email": "e@x"})
    assert IapIdentity(AUD, verify).identify({"x-goog-iap-jwt-assertion": "t"}).id == ok_128
    assert (
        IapIdentity(AUD, Verify({"sub": "x:Ab_9-z", "email": "e@x"}))
        .identify({"x-goog-iap-jwt-assertion": "t"})
        .id
        == "Ab_9-z"
    )
    for bad in ("a" * 129, "", "12 34", "a/b", "..", "a.b", "ïd"):
        verify = Verify({"sub": f"accounts.google.com:{bad}", "email": "e@x"})
        with pytest.raises(IdentityError):
            IapIdentity(AUD, verify).identify({"x-goog-iap-jwt-assertion": "t"})


def test_fixed_identity_always_returns_the_same_person() -> None:
    me = Identity("local-owner", "owner@localhost")
    fixed = FixedIdentity(me)
    assert fixed.identify({}) == me
    assert fixed.identify({"x-goog-iap-jwt-assertion": "someone-else"}) == me


def test_make_identity_local_is_fixed_and_cloud_is_iap() -> None:
    local = make_identity(Settings(local=True, local_user_id="me-1", local_user_email="me@here"))
    assert isinstance(local, FixedIdentity)
    assert local.identify({}) == Identity("me-1", "me@here")
    cloud = make_identity(Settings(users_bucket="u", system_bucket="s", owner_email="o@x", iap_audience=AUD))
    assert isinstance(cloud, IapIdentity)
    with pytest.raises(IdentityError):
        cloud.identify({})
