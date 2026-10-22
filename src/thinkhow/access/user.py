"""CurrentUser from the verified identity; the owner is one email in the settings (M3 A4)."""

from dataclasses import dataclass

from thinkhow.platform.config import Settings
from thinkhow.platform.identity import Identity


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    is_owner: bool


def current_user(identity: Identity, settings: Settings) -> CurrentUser:
    owner = settings.owner_email.strip().lower()
    is_owner = bool(owner) and identity.email.strip().lower() == owner
    return CurrentUser(id=identity.id, email=identity.email, is_owner=is_owner)
