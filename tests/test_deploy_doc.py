"""Seam 3 of skel-guards-deploy: docs/deploy.md agrees with the code it deploys."""

from pathlib import Path

from thinkhow.platform.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")


def command(phrase: str) -> str:
    lines = DOC.splitlines()
    start = next(i for i, line in enumerate(lines) if phrase in line)
    end = start
    while lines[end].rstrip().endswith("\\"):
        end += 1
    return "\n".join(lines[start : end + 1])


def test_every_cloud_setting_stands_in_the_job_and_in_the_service() -> None:
    required = ("users_bucket", "system_bucket", "owner_email")
    assert all(name in Settings.model_fields for name in (*required, "iap_audience"))
    for phrase in ("gcloud run jobs deploy thinkhow-learning", "gcloud run deploy thinkhow"):
        for name in required:
            assert f"THINKHOW_{name.upper()}=" in command(phrase), (phrase, name)
    assert "THINKHOW_IAP_AUDIENCE=" in command("gcloud run deploy thinkhow")


def test_seed_runs_before_the_service_is_deployed() -> None:
    assert DOC.index("thinkhow.learning.job,seed") < DOC.index("gcloud run deploy thinkhow")
