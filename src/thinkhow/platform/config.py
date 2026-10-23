"""Settings from environment variables (M3 A4). Refuses local mode inside Cloud Run (M3 A2, G4).

Does NOT build adapters from the settings — that is make_storage / make_llm / make_identity.
"""

from collections.abc import Mapping
from pathlib import Path

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class ConfigError(Exception):
    """The environment cannot run ThinkHow as configured."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="THINKHOW_", extra="ignore")

    local: bool = False
    project: str = "pocket-lawyer-431614"
    location: str = "eu"
    model: str = "gemini-4-argon"
    users_bucket: str = ""
    system_bucket: str = ""
    local_dir: Path = Path(".local-data")
    owner_email: str = ""
    iap_audience: str = ""
    local_user_id: str = "local-owner"
    local_user_email: str = "owner@localhost"
    llm_timeout_s: float = 300.0
    llm_attempts: int = 3
    speech_model: str = "gemini-3.5-transcribe"
    speech_timeout_s: float = 120.0

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Only what load_settings passes in: the environment is injected, never read behind its back."""
        return (init_settings,)


PREFIX = "THINKHOW_"
CLOUD_RUN_MARKERS = ("K_SERVICE", "CLOUD_RUN_JOB")


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Flow: read the THINKHOW_* values of `environ` only → refuse what cannot run."""
    settings = Settings.model_validate(_prefixed_values(environ))
    _refuse_local_in_cloud_run(settings, environ)
    _refuse_cloud_without_resources(settings)
    return settings


def _prefixed_values(environ: Mapping[str, str]) -> dict[str, str]:
    return {key[len(PREFIX) :].lower(): value for key, value in environ.items() if key.startswith(PREFIX)}


def _refuse_local_in_cloud_run(settings: Settings, environ: Mapping[str, str]) -> None:
    if settings.local and any(marker in environ for marker in CLOUD_RUN_MARKERS):
        raise ConfigError("local mode refuses to start inside Cloud Run: it would make everyone one person")


def _refuse_cloud_without_resources(settings: Settings) -> None:
    if settings.local:
        return
    required = ("users_bucket", "system_bucket", "owner_email")
    missing = [name for name in required if not getattr(settings, name)]
    if missing:
        raise ConfigError(f"set THINKHOW_{', THINKHOW_'.join(m.upper() for m in missing)}")
