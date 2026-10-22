"""Helpers for the skel-knowledge contract tests (slice tester). Built from the contract, not the code.

- RecordingStorage: a LocalStorage that records every write / create_if_absent (bucket, path,
  content type) and can raise on the N-th create_if_absent (Seam 1: a seeding run that fails halfway)
  or force the result of create_if_absent for one path.
- card_dict / write_card: valid cards for a temporary `cards_dir`, as YAML files.
- snapshot: every file under a LocalStorage root with its bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from thinkhow.platform.storage import Bucket, LocalStorage


class Boom(RuntimeError):
    """The failure the fake storage injects."""


class RecordingStorage(LocalStorage):
    def __init__(
        self, root: Path, fail_on_create: int | None = None, forced: dict[str, bool] | None = None
    ) -> None:
        super().__init__(root)
        self.fail_on_create = fail_on_create
        self.forced = forced or {}
        self.creates: list[tuple[Bucket, str, str]] = []
        self.writes: list[tuple[Bucket, str, str]] = []

    def write(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> None:
        self.writes.append((bucket, path, content_type))
        super().write(bucket, path, data, content_type)

    def create_if_absent(self, bucket: Bucket, path: str, data: bytes, content_type: str) -> bool:
        self.creates.append((bucket, path, content_type))
        if self.fail_on_create is not None and len(self.creates) == self.fail_on_create:
            raise Boom(f"injected failure on create_if_absent #{self.fail_on_create}: {path}")
        if path in self.forced:
            return self.forced[path]
        return super().create_if_absent(bucket, path, data, content_type)


def phase_dict(pid: str, *, exit_text: str | None = None, skip_if: str | None = None) -> dict[str, Any]:
    # The texts carry the id upper-cased, so that finding the id itself in a prompt proves the id was
    # written, not just the title or the goal that happen to contain it.
    tag = pid.upper()
    phase: dict[str, Any] = {
        "id": pid,
        "title": f"Фаза {tag}",
        "goal": f"мета фази {tag}",
        "how": [f"як-1 фази {tag}", f"як-2 фази {tag}"],
        "exit": exit_text if exit_text is not None else f"вихід фази {tag}",
    }
    if skip_if is not None:
        phase["skip_if"] = skip_if
    return phase


def card_dict(
    cid: str, title: str | None = None, phases: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title if title is not None else f"Картка {cid}",
        "router": {
            "needs": f"роутер-потреба {cid}",
            "when_yes": [f"роутер-так {cid}"],
            "when_no": [f"роутер-ні {cid}"],
            "signals": [f"роутер-сигнал {cid}"],
        },
        "facilitator": {
            "purpose": f"навіщо {cid}",
            "stance": f"позиція {cid}",
            "needs": f"на вході {cid}",
            "phases": phases if phases is not None else [phase_dict("p_one"), phase_dict("p_two")],
            "ending": f"чим закінчується {cid}",
            "traps": [{"name": f"пастка-назва {cid}", "text": f"пастка-текст {cid}"}],
            "pairs_well": f"поєднується {cid}",
        },
    }


def write_card(cards_dir: Path, data: dict[str, Any], stem: str | None = None) -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{stem if stem is not None else data['id']}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def put_json(store: LocalStorage, path: str, data: dict[str, Any]) -> None:
    store.write("system", path, json.dumps(data, ensure_ascii=False).encode(), "application/json")


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
