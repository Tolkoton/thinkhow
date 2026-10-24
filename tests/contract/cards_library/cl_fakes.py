"""Helpers for the cards-library contract tests (slice tester). Built from the contract, not the code.

- RecordingStorage: a LocalStorage that records every write / create_if_absent (bucket, path, content type),
  can raise on the N-th create_if_absent (a storage that refuses halfway) and can force the result of
  create_if_absent for one path or for every path under a prefix (another run created it first).
- card_dict / write_card: valid cards for a temporary `cards_dir`, as YAML files.
- put_card / put_memory / put_change: Knowledge written by hand (revisions, stray version files).
- snapshot: every file under a LocalStorage root with its bytes.
- LogCapture / local_environ: the Job's JSON log lines and a local-mode environment.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import thinkhow.platform.log as log
from thinkhow.knowledge import ChangeRecord
from thinkhow.platform.storage import Bucket, LocalStorage

REPO = Path(__file__).resolve().parents[3]
REPO_CARDS = REPO / "cards"
CHANGES = "knowledge/changes/"
WHY = "нова ревізія з теки cards/ репозиторію (Job cards)"


class Boom(RuntimeError):
    """The failure the fake storage injects."""


class RecordingStorage(LocalStorage):
    def __init__(
        self,
        root: Path,
        fail_on_create: int | None = None,
        forced: dict[str, bool] | None = None,
        forced_prefix: tuple[str, bool] | None = None,
    ) -> None:
        super().__init__(root)
        self.fail_on_create = fail_on_create
        self.forced = forced or {}
        self.forced_prefix = forced_prefix
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
        if self.forced_prefix is not None and path.startswith(self.forced_prefix[0]):
            return self.forced_prefix[1]
        return super().create_if_absent(bucket, path, data, content_type)


def card_dict(cid: str, title: str | None = None) -> dict[str, Any]:
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
            "phases": [
                {"id": "p_one", "title": "Фаза 1", "goal": "мета 1", "how": ["як 1"], "exit": "вихід 1"},
                {"id": "p_two", "title": "Фаза 2", "goal": "мета 2", "how": ["як 2"], "exit": "вихід 2"},
            ],
            "ending": f"чим закінчується {cid}",
            "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
            "pairs_well": f"поєднується {cid}",
        },
    }


def memory_dict(mid: str, card: str) -> dict[str, Any]:
    return {
        "id": mid,
        "title": f"запис {mid}",
        "cards": [card],
        "noticed": "помічено",
        "do": "робити",
        "basis": "підстава",
    }


def write_card(cards_dir: Path, data: dict[str, Any], stem: str | None = None) -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{stem if stem is not None else data['id']}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def write_cards(cards_dir: Path, cards: dict[str, str]) -> Path:
    """cards: id -> title."""
    cards_dir.mkdir(parents=True, exist_ok=True)
    for cid, title in cards.items():
        write_card(cards_dir, card_dict(cid, title))
    return cards_dir


def put_json(store: LocalStorage, path: str, data: dict[str, Any]) -> None:
    store.write("system", path, json.dumps(data, ensure_ascii=False).encode(), "application/json")


def put_card(store: LocalStorage, cid: str, k: int, title: str) -> str:
    path = f"knowledge/cards/{cid}/v{k}.json"
    put_json(store, path, card_dict(cid, title))
    return path


def put_memory(store: LocalStorage, mid: str, k: int, card: str) -> str:
    path = f"knowledge/memory/{mid}/v{k}.json"
    put_json(store, path, memory_dict(mid, card))
    return path


def put_change(
    store: LocalStorage, rev: int, cards: dict[str, str], memory: dict[str, str] | None = None
) -> None:
    record = {"rev": rev, "what": f"зміна {rev}", "why": "чому", "cards": cards, "memory": memory or {}}
    put_json(store, f"{CHANGES}{rev:06d}.json", record)


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def change_files(store: LocalStorage) -> list[str]:
    return sorted(store.list("system", CHANGES))


def new_change(store: LocalStorage, before: list[str]) -> ChangeRecord:
    """The one change record that appeared since `before`."""
    added = [p for p in change_files(store) if p not in before]
    assert len(added) == 1, added
    data = store.read("system", added[0])
    assert data is not None
    return ChangeRecord.model_validate_json(data)


class LogCapture:
    def __init__(self, capsys: Any) -> None:
        self.buffer = io.StringIO()
        self.capsys = capsys
        self._out = ""
        self._err = ""

    def _read(self) -> None:
        got = self.capsys.readouterr()
        self._out += got.out
        self._err += got.err

    def err(self) -> str:
        self._read()
        return self._err

    def events(self, name: str) -> list[dict[str, Any]]:
        self._read()
        found: list[dict[str, Any]] = []
        for line in (self.buffer.getvalue() + "\n" + self._out + "\n" + self._err).splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("event") == name:
                found.append(obj)
        return found


def install_log_capture(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> LogCapture:
    cap = LogCapture(capsys)
    monkeypatch.setattr(log.log_event, "__defaults__", (cap.buffer,))
    return cap


def local_environ(root: Path) -> dict[str, str]:
    return {
        "THINKHOW_LOCAL": "true",
        "THINKHOW_LOCAL_DIR": str(root),
        "THINKHOW_OWNER_EMAIL": "owner@localhost",
    }
