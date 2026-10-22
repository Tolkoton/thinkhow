"""DISPUTED (Q6): a `sub` with no ':' gives the whole `sub` as the id. Not sealed until answered."""

from thinkhow.platform.identity import IapIdentity, Identity


def test_q6_sub_without_colon_is_the_whole_id() -> None:
    def verify(token: str, audience: str) -> dict[str, object]:
        return {"sub": "1234567890", "email": "ann@example.com"}

    who = IapIdentity("aud", verify).identify({"x-goog-iap-jwt-assertion": "t"})
    assert who == Identity("1234567890", "ann@example.com")
