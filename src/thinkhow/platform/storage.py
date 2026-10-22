"""File storage: Cloud Storage, or a local folder in local mode (M2 S2, M3 A2).

Does NOT delete files, cache, or know what the files mean.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Protocol

from google.api_core.exceptions import NotFound, PreconditionFailed

from thinkhow.platform.config import Settings

Bucket = Literal["users", "system"]


class Storage(Protocol):
    def read(self, bucket: Bucket, path: str) -> bytes | None: ...

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None: ...

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool: ...

    def list(self, bucket: Bucket, prefix: str) -> list[str]: ...


def check_path(path: str) -> str:
    """A relative path of plain segments; anything else never reaches the disk or Cloud Storage (I3)."""
    if path.startswith("/") or any(seg in ("", ".", "..") for seg in path.split("/")):
        raise ValueError(f"unsafe storage path: {path!r}")
    return path


def check_prefix(prefix: str) -> str:
    """A listing prefix, Cloud Storage semantics: '' and a trailing '/' are lawful; the rest as check_path."""
    if prefix == "":
        return prefix
    check_path(prefix[:-1] if prefix.endswith("/") else prefix)
    return prefix


class LocalStorage:
    """`<root>/<bucket>/<path>` on the local disk: tests and local development."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _file(self, bucket: Bucket, path: str) -> Path:
        return self.root / bucket / check_path(path)

    def read(self, bucket: Bucket, path: str) -> bytes | None:
        file = self._file(bucket, path)
        return file.read_bytes() if file.is_file() else None

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        file = self._file(bucket, path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        file = self._file(bucket, path)
        file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with file.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            return False
        return True

    def list(self, bucket: Bucket, prefix: str) -> list[str]:
        check_prefix(prefix)
        base = self.root / bucket
        if not base.is_dir():
            return []
        names = (p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())
        return sorted(name for name in names if name.startswith(prefix))


class GcsStorage:
    """Cloud Storage through the client library (M2 S2: not a mounted folder)."""

    def __init__(self, client: Any, names: Mapping[Bucket, str]) -> None:
        self.client = client
        self.names = names

    def _blob(self, bucket: Bucket, path: str) -> Any:
        return self.client.bucket(self.names[bucket]).blob(check_path(path))

    def read(self, bucket: Bucket, path: str) -> bytes | None:
        try:
            data: bytes = self._blob(bucket, path).download_as_bytes()
        except NotFound:
            return None
        return data

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self._blob(bucket, path).upload_from_string(data, content_type=content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        try:
            blob = self._blob(bucket, path)
            blob.upload_from_string(data, content_type=content_type, if_generation_match=0)
        except PreconditionFailed:
            return False
        return True

    def list(self, bucket: Bucket, prefix: str) -> list[str]:
        blobs = self.client.list_blobs(self.names[bucket], prefix=check_prefix(prefix))
        return sorted(blob.name for blob in blobs)


def make_storage(settings: Settings) -> Storage:
    if settings.local:
        return LocalStorage(settings.local_dir)
    from google.cloud import storage as gcs

    names: dict[Bucket, str] = {"users": settings.users_bucket, "system": settings.system_bucket}
    return GcsStorage(gcs.Client(project=settings.project), names)
