"""Task 705: the web service refuses the cloud without THINKHOW_IAP_AUDIENCE; the Job does not need it."""

from pathlib import Path

import pytest

from thinkhow.platform.config import ConfigError, load_settings
from thinkhow.web import app

CLOUD = {
    "THINKHOW_USERS_BUCKET": "th-users",
    "THINKHOW_SYSTEM_BUCKET": "th-system",
    "THINKHOW_OWNER_EMAIL": "owner@example.com",
}


def test_web_service_in_the_cloud_without_an_iap_audience_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_storage(settings: object) -> object:
        raise AssertionError("storage was built before the IAP audience was checked")

    monkeypatch.setattr(app, "make_storage", no_storage)
    with pytest.raises(ConfigError, match="THINKHOW_IAP_AUDIENCE"):
        app.build_deps(CLOUD, tmp_path)


def test_the_job_settings_in_the_cloud_need_no_iap_audience() -> None:
    assert load_settings(CLOUD).iap_audience == ""
