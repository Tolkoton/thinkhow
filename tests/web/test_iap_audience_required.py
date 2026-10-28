"""Task 705: the web service refuses the cloud without THINKHOW_IAP_AUDIENCE; the Job does not need it."""

import os
from pathlib import Path

import pytest

from thinkhow.platform.config import ConfigError, load_settings
from thinkhow.web import app

CLOUD = {
    "THINKHOW_USERS_BUCKET": "th-users",
    "THINKHOW_SYSTEM_BUCKET": "th-system",
    "THINKHOW_OWNER_EMAIL": "owner@example.com",
}


@pytest.fixture(autouse=True)
def cloud_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("THINKHOW_"):
            monkeypatch.delenv(key)
    for key, value in CLOUD.items():
        monkeypatch.setenv(key, value)


def test_the_service_entry_point_in_the_cloud_without_an_iap_audience_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_deps(environ: object, cards_dir: Path) -> object:
        raise AssertionError("deps were built before the IAP audience was checked")

    monkeypatch.setattr(app, "build_deps", no_deps)
    with pytest.raises(ConfigError, match="THINKHOW_IAP_AUDIENCE"):
        app.app  # noqa: B018 — the attribute uvicorn imports (Dockerfile CMD thinkhow.web.app:app)


def test_the_entry_point_with_an_iap_audience_goes_on_to_build_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THINKHOW_IAP_AUDIENCE", "/projects/1/locations/europe-west3/services/thinkhow")
    built: list[str] = []

    def stop_at_deps(environ: object, cards_dir: Path) -> object:
        built.append("deps")
        raise RuntimeError("stop here")

    monkeypatch.setattr(app, "build_deps", stop_at_deps)
    with pytest.raises(RuntimeError, match="stop here"):
        app.app  # noqa: B018
    assert built == ["deps"]


def test_the_job_settings_in_the_cloud_need_no_iap_audience() -> None:
    assert load_settings(CLOUD).iap_audience == ""
