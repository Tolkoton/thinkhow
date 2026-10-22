"""DISPUTED (Q5): `K_SERVICE` / `CLOUD_RUN_JOB` count as "present in environ" even with an empty value.
Not sealed until answered."""

import os

import pytest

from thinkhow.platform.config import ConfigError, load_settings


def test_q5_cloud_run_variable_with_empty_value_still_refuses_local(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("THINKHOW_") or key in ("K_SERVICE", "CLOUD_RUN_JOB"):
            monkeypatch.delenv(key)
    for environ in (
        {"THINKHOW_LOCAL": "true", "K_SERVICE": ""},
        {"THINKHOW_LOCAL": "true", "CLOUD_RUN_JOB": ""},
    ):
        with pytest.raises(ConfigError):
            load_settings(environ)
