"""Auto-deploy (task 601): the version a board task closed goes to Cloud Run by itself.

Run by cron on this server every few minutes: `python3 scripts/auto_deploy.py` (docs/deploy.md, section 11).
Does what Сонько did by hand (`~/sonko/done/2026-11-04-thinkhow-deploy-311-document-upload.request.md`):
- the snapshot is the latest `board: <task> → done` commit of the work branch, unpacked with `git archive` —
  never the working tree, never a commit whose own `tasks/doing/` still holds a task;
- nothing happens when the service already runs that commit or nothing that goes into the image changed;
- before the build and again before the update nobody writes (no `POST …/reply` in the last 15 minutes),
  otherwise the next run tries again;
- Job `thinkhow-learning` and service `thinkhow` get the new image and nothing else; when `cards/` or
  `notes/` changed, the Job's `cards` / `notes` runs between the two (both repeat safely; never `seed`);
- on an error nothing is rolled back: a line in the journal, a question in `tasks/blocked/`, and that
  commit is not tried again (`--retry` does).
Only the standard library: cron runs it with the system python3.
"""

from __future__ import annotations

import argparse
import fcntl
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT = "pocket-lawyer-431614"
REGION = "europe-west3"
SERVICE = "thinkhow"
JOB = "thinkhow-learning"
REPOSITORY = f"{REGION}-docker.pkg.dev/{PROJECT}/thinkhow/thinkhow"
BRANCH = "unattended/work"
# What the Dockerfile copies into the image; tests/test_auto_deploy.py holds this list to the Dockerfile.
IMAGE_PATHS = ("Dockerfile", "pyproject.toml", "uv.lock", "src", "cards", "notes")
# A changed path among these runs the Job command of its name before the service (docs/deploy.md, 7, 8a).
KNOWLEDGE_PATHS = ("cards", "notes")
DONE = re.compile(r"^board: (\S+) → done")
WRITING = (
    f'resource.type="cloud_run_revision" AND resource.labels.service_name="{SERVICE}" '
    'AND httpRequest.requestMethod="POST" AND httpRequest.requestUrl=~"/reply"'
)
ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("THINKHOW_DEPLOY_STATE", Path.home() / ".local" / "state" / "thinkhow-deploy"))


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


Run = Callable[[Sequence[str]], Result]
Notify = Callable[[str, str, str], None]


class DeployFailed(Exception):
    def __init__(self, step: str, result: Result) -> None:
        super().__init__(step)
        self.step = step
        self.result = result


def shell(cmd: Sequence[str]) -> Result:
    done = subprocess.run(list(cmd), capture_output=True, text=True, check=False)
    return Result(done.returncode, done.stdout, done.stderr)


def deploy(
    repo: Path, state: Path, run: Run, notify: Notify, retry: bool = False, dry_run: bool = False
) -> str:
    """One pass. Returns what happened, one line; the journal gets the deployments and the failures."""
    if (state / "off").exists():
        return "off: the stop file is there"
    candidate = latest_done(repo)
    if candidate is None:
        return "nothing: no → done commit on the branch"
    sha, task = candidate
    short = sha[:7]
    if unfinished(repo, sha):
        return f"skip {short}: tasks/doing/ in that commit still holds a task"
    try:
        return release(repo, state, run, sha, task, retry, dry_run)
    except DeployFailed as failure:
        if dry_run:
            return f"failed {short}: {failure.step} (dry run, nothing recorded)"
        what = (
            f"{failure.step}: exit {failure.result.code}\n{failure.result.out}\n{failure.result.err}".strip()
        )
        journal(state, f"failed {short} {task} {failure.step}")
        notify(short, task, what)
        return f"failed {short}: {failure.step}"


def release(repo: Path, state: Path, run: Run, sha: str, task: str, retry: bool, dry_run: bool) -> str:
    short = sha[:7]
    running = gcloud(
        run,
        "describe",
        "run",
        "services",
        "describe",
        SERVICE,
        "--format=value(spec.template.spec.containers[0].image)",
    ).strip()
    base = known_commit(repo, running.rsplit(":", 1)[-1]) if ":" in running else None
    if base is not None:
        if base == sha:
            return f"up to date: {short}"
        if not is_ancestor(repo, base, sha):
            return f"skip {short}: the service runs {base[:7]}, which is not before it"
        if not changed(repo, base, sha, IMAGE_PATHS):
            return f"up to date: nothing for the image changed since {base[:7]}"
    if not retry and short in failed(state):
        return f"skip {short}: it failed before (--retry tries again)"
    if writing(run):
        return f"later {short}: somebody writes"
    commands = [path for path in KNOWLEDGE_PATHS if base is None or changed(repo, base, sha, (path,))]
    if dry_run:
        return f"would deploy {short} ({task}), Job commands: {', '.join(commands) or '—'}"
    image = f"{REPOSITORY}:{short}"
    with tempfile.TemporaryDirectory(prefix=f"thinkhow-{short}-") as tmp:
        unpack(repo, sha, Path(tmp))
        gcloud(run, "build", "builds", "submit", "--tag", image, tmp, region=False)
    if writing(run):
        return f"later {short}: somebody writes (the image is built)"
    gcloud(run, "job", "run", "jobs", "update", JOB, f"--image={image}")
    for command in commands:
        gcloud(
            run,
            f"job-{command}",
            "run",
            "jobs",
            "execute",
            JOB,
            "--wait",
            f"--args=-m,thinkhow.learning.job,{command}",
        )
    gcloud(run, "service", "run", "services", "update", SERVICE, f"--image={image}")
    now = gcloud(
        run,
        "check",
        "run",
        "services",
        "describe",
        SERVICE,
        "--format=value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)",
    ).split()
    if image not in now:
        raise DeployFailed("check", Result(1, " ".join(now), f"the service does not run {image}"))
    tasks = " ".join(done_tasks(repo, base, sha))
    jobs = f" job={','.join(commands)}" if commands else ""
    journal(state, f"deployed {short} {tasks} revision={now[0]}{jobs}")
    return f"deployed {short}"


def gcloud(run: Run, step: str, *args: str, region: bool = True) -> str:
    result = run(["gcloud", *args, f"--project={PROJECT}", *([f"--region={REGION}"] if region else [])])
    if result.code != 0:
        raise DeployFailed(step, result)
    return result.out


def writing(run: Run) -> bool:
    result = run(
        [
            "gcloud",
            "logging",
            "read",
            WRITING,
            f"--project={PROJECT}",
            "--freshness=15m",
            "--limit=1",
            "--format=value(timestamp)",
        ]
    )
    if result.code != 0:
        raise DeployFailed("logging", result)
    return bool(result.out.strip())


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def latest_done(repo: Path) -> tuple[str, str] | None:
    for line in git(repo, "log", "-n", "500", "--format=%H%x09%s", BRANCH).splitlines():
        sha, _, subject = line.partition("\t")
        found = DONE.match(subject)
        if found:
            return sha, found.group(1)
    return None


def unfinished(repo: Path, sha: str) -> bool:
    return any(
        name.endswith(".md") for name in git(repo, "ls-tree", "--name-only", sha, "tasks/doing/").split()
    )


def known_commit(repo: Path, ref: str) -> str | None:
    if not re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return None
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() or None


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", older, newer],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def changed(repo: Path, base: str, sha: str, paths: Sequence[str]) -> bool:
    return bool(git(repo, "diff", "--name-only", base, sha, "--", *paths).strip())


def done_tasks(repo: Path, base: str | None, sha: str) -> list[str]:
    span = [f"{base}..{sha}"] if base else ["-n", "1", sha]
    subjects = git(repo, "log", "--format=%s", *span).splitlines()
    return [found.group(1) for found in map(DONE.match, reversed(subjects)) if found]


def unpack(repo: Path, sha: str, into: Path) -> None:
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", sha], capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")


def failed(state: Path) -> set[str]:
    log = state / "journal.log"
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return {parts[2] for parts in map(str.split, lines) if len(parts) > 2 and parts[1] == "failed"}


def journal(state: Path, line: str) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with (state / "journal.log").open("a", encoding="utf-8") as log:
        log.write(f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} {line}\n")


def board_question(repo: Path) -> Notify:
    """A failed deployment becomes a question in tasks/blocked/ (board.py open-item), one per commit."""

    def notify(short: str, task: str, what: str) -> None:
        subprocess.run(
            [
                "python3",
                str(ROOT / ".claude" / "unattended" / "board.py"),
                f"--root={repo}",
                "open-item",
                "--to",
                "blocked",
                "--key",
                f"auto-deploy-{short}",
                "--source",
                "auto-deploy (scripts/auto_deploy.py)",
                "--title",
                f"Автоматичне розгортання {short} не вдалося",
                "--what",
                f"Версію {short} (задача {task}) не розгорнуто; нічого не відкочено, сервіс працює на "
                f"попередній версії. Вивід: {what[-1500:]}",
                "--question",
                "Що зробити з цією версією? Сам механізм її вдруге не пробуватиме; наступна "
                "завершена задача спробує свою. Варіанти: (а) нічого — чекати наступної задачі; "
                "(б) Сонько повторює цю версію: `python3 scripts/auto_deploy.py --retry`; "
                "(в) агент розбирається з причиною окремою задачею. Порада: (б), якщо вивід схожий "
                "на тимчасовий збій мережі чи входу в gcloud, інакше (в).",
            ],
            cwd=repo,
            capture_output=True,
            check=False,
        )

    return notify


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy the latest → done commit to Cloud Run (task 601).")
    parser.add_argument("--retry", action="store_true", help="try again a commit that failed before")
    parser.add_argument("--dry-run", action="store_true", help="read-only: say what would be deployed")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print the outcome even when nothing happens"
    )
    args = parser.parse_args(argv)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        outcome = deploy(ROOT, STATE, shell, board_question(ROOT), retry=args.retry, dry_run=args.dry_run)
    if args.verbose or args.dry_run or outcome.startswith(("deployed", "failed", "later")):
        print(f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} {outcome}")
    return 1 if outcome.startswith("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
