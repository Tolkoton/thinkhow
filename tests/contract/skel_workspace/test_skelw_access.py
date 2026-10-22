"""Contract tests of skel-workspace: access.current_user (slice tester; from the contract, not the code)."""

from thinkhow.access import CurrentUser, current_user
from thinkhow.platform.config import Settings
from thinkhow.platform.identity import Identity


def test_owner_email_matches_ignoring_case_and_edge_spaces() -> None:
    settings = Settings(owner_email=" Owner@Example.COM ")
    got = current_user(Identity(id="u-1", email="owner@example.com"), settings)
    assert got == CurrentUser(id="u-1", email="owner@example.com", is_owner=True)
    got2 = current_user(
        Identity(id="u-1", email="  OWNER@example.com"), Settings(owner_email="owner@example.com")
    )
    assert got2.is_owner is True


def test_other_email_is_not_the_owner() -> None:
    settings = Settings(owner_email="owner@example.com")
    got = current_user(Identity(id="u-2", email="someone@example.com"), settings)
    assert got == CurrentUser(id="u-2", email="someone@example.com", is_owner=False)
    assert current_user(Identity(id="u-3", email="owner@example.co"), settings).is_owner is False


def test_empty_owner_email_makes_nobody_the_owner() -> None:
    settings = Settings(owner_email="")
    assert current_user(Identity(id="local-owner", email="owner@localhost"), settings).is_owner is False
