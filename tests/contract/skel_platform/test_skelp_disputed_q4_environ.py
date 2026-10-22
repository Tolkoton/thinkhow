"""DISPUTED (Q4): load_settings reads ONLY the `environ` it is given, never the process environment.
Not sealed until answered."""

import os

import pytest

from thinkhow.platform.config import ConfigError, load_settings

CLOUD = {
    "THINKHOW_USERS_BUCKET": "th-users",
    "THINKHOW_SYSTEM_BUCKET": "th-system",
    "THINKHOW_OWNER_EMAIL": "owner@example.com",
}


def test_q4_process_environment_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("THINKHOW_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("THINKHOW_MODEL", "from-process")
    monkeypatch.setenv("THINKHOW_USERS_BUCKET", "from-process")
    monkeypatch.setenv("THINKHOW_SYSTEM_BUCKET", "from-process")
    monkeypatch.setenv("THINKHOW_OWNER_EMAIL", "from@process")
    assert load_settings(CLOUD).model == "gemini-4-argon"
    with pytest.raises(ConfigError):
        load_settings({})
