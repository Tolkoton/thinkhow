"""Contract tests of skel-platform: config.py (slice tester; written from the contract, not the code)."""

import os

import pytest

from thinkhow.platform.config import ConfigError, Settings, load_settings

CLOUD = {
    "THINKHOW_USERS_BUCKET": "th-users",
    "THINKHOW_SYSTEM_BUCKET": "th-system",
    "THINKHOW_OWNER_EMAIL": "owner@example.com",
}


@pytest.fixture(autouse=True)
def clean_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("THINKHOW_") or key in ("K_SERVICE", "CLOUD_RUN_JOB"):
            monkeypatch.delenv(key)


def test_load_settings_reads_prefixed_values_and_keeps_defaults() -> None:
    settings = load_settings(
        {**CLOUD, "THINKHOW_LLM_ATTEMPTS": "5", "THINKHOW_IAP_AUDIENCE": "/projects/1/x"}
    )
    assert isinstance(settings, Settings)
    assert settings.users_bucket == "th-users"
    assert settings.system_bucket == "th-system"
    assert settings.owner_email == "owner@example.com"
    assert settings.llm_attempts == 5
    assert settings.iap_audience == "/projects/1/x"
    assert settings.local is False
    assert settings.model == "gemini-4-argon"
    assert settings.location == "eu"
    assert settings.llm_timeout_s == 300.0


def test_cloud_mode_without_a_bucket_or_owner_email_is_a_config_error() -> None:
    for missing in CLOUD:
        environ = {k: v for k, v in CLOUD.items() if k != missing}
        with pytest.raises(ConfigError):
            load_settings(environ)
    with pytest.raises(ConfigError):
        load_settings({})


def test_local_mode_outside_cloud_run_needs_no_buckets() -> None:
    settings = load_settings({"THINKHOW_LOCAL": "true"})
    assert settings.local is True


def test_cloud_mode_inside_cloud_run_is_allowed() -> None:
    assert load_settings({**CLOUD, "K_SERVICE": "thinkhow"}).local is False
    assert load_settings({**CLOUD, "CLOUD_RUN_JOB": "thinkhow-learn"}).local is False


def test_I4_local_mode_never_starts_in_cloud_run() -> None:
    cases = [
        {"THINKHOW_LOCAL": "true", "K_SERVICE": "thinkhow"},
        {"THINKHOW_LOCAL": "1", "K_SERVICE": "thinkhow"},
        {"THINKHOW_LOCAL": "true", "CLOUD_RUN_JOB": "thinkhow-learn"},
        {"THINKHOW_LOCAL": "1", "CLOUD_RUN_JOB": "thinkhow-learn"},
        {"THINKHOW_LOCAL": "true", "K_SERVICE": "thinkhow", "CLOUD_RUN_JOB": "thinkhow-learn"},
        # every cloud field filled in does not make local mode lawful in Cloud Run
        {**CLOUD, "THINKHOW_LOCAL": "true", "CLOUD_RUN_JOB": "thinkhow-learn"},
        {**CLOUD, "THINKHOW_LOCAL": "true", "K_SERVICE": "thinkhow"},
    ]
    for environ in cases:
        with pytest.raises(ConfigError):
            load_settings(environ)
