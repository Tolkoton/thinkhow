"""Task 601: scripts/auto_deploy.py against a real git repository and a fake gcloud."""

import importlib.util
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("auto_deploy", ROOT / "scripts" / "auto_deploy.py")
assert _spec and _spec.loader
ad = importlib.util.module_from_spec(_spec)
sys.modules["auto_deploy"] = ad
_spec.loader.exec_module(ad)


class Gcloud:
    """Answers like gcloud; records every call and what the build context held."""

    def __init__(self, running: str = "skeleton", writing: Sequence[bool] = (False,), fail: str = "") -> None:
        self.running = running
        self.writing = list(writing)
        self.fail = fail
        self.calls: list[list[str]] = []
        self.built: dict[str, str] = {}

    def __call__(self, cmd: Sequence[str]) -> object:
        cmd = list(cmd)
        self.calls.append(cmd)
        line = " ".join(cmd)
        if self.fail and self.fail in line:
            return ad.Result(1, "", "ERROR: boom")
        if cmd[1:3] == ["logging", "read"]:
            busy = self.writing.pop(0) if len(self.writing) > 1 else self.writing[0]
            return ad.Result(0, "2026-11-04T20:00:00Z\n" if busy else "", "")
        if cmd[1:3] == ["builds", "submit"]:
            context = Path(cmd[cmd.index("--tag") + 2])
            self.built = {
                str(p.relative_to(context)): p.read_text() for p in context.rglob("*") if p.is_file()
            }
            return ad.Result(0, "SUCCESS", "")
        if cmd[1:4] == ["run", "services", "update"]:
            self.running = cmd[5].removeprefix("--image=")
            return ad.Result(0, "", "")
        if cmd[1:4] == ["run", "services", "describe"]:
            fmt = next(a for a in cmd if a.startswith("--format="))
            if "latestReadyRevisionName" in fmt:
                return ad.Result(0, f"thinkhow-00016-abc\t{self.running}\n", "")
            return ad.Result(
                0, f"{ad.REPOSITORY}:{self.running}\n" if ":" not in self.running else self.running, ""
            )
        return ad.Result(0, "", "")

    def steps(self) -> list[str]:
        return [" ".join(c[1:4]) for c in self.calls if c[1] != "logging" and "describe" not in c]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def commit(repo: Path, subject: str, files: dict[str, str | None]) -> str:
    for name, text in files.items():
        path = repo / name
        if text is None:
            git(repo, "rm", "-q", name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git(repo, "add", name)
    git(repo, "commit", "-q", "--allow-empty", "-m", subject)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", ad.BRANCH)
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    commit(
        repo,
        "start",
        {
            "Dockerfile": "FROM x\n",
            "src/app.py": "v1\n",
            "cards/a.yaml": "a\n",
            "notes/a.yaml": "n\n",
            "tasks/doing/.gitkeep": "",
            "docs/x.md": "d\n",
        },
    )
    return repo


def deploy(repo: Path, gcloud: Gcloud, retry: bool = False) -> tuple[str, list[tuple[str, str, str]]]:
    told: list[tuple[str, str, str]] = []
    outcome = ad.deploy(repo, repo.parent / "state", gcloud, lambda *a: told.append(a), retry=retry)
    return outcome, told


def journal(repo: Path) -> str:
    log = repo.parent / "state" / "journal.log"
    return log.read_text() if log.exists() else ""


def test_deploys_the_snapshot_of_the_done_commit_not_the_working_tree(repo: Path) -> None:
    commit(repo, "board: 100-a → doing", {"tasks/doing/100-a.md": "a\n"})
    commit(repo, "code", {"src/app.py": "v2\n"})
    done = commit(
        repo, "board: 100-a → done — x", {"tasks/doing/100-a.md": None, "tasks/done/100-a/task.md": "a\n"}
    )
    commit(repo, "board: 101-b → doing", {"tasks/doing/101-b.md": "b\n"})
    commit(repo, "code of b, committed mid-task", {"src/app.py": "v3-committed\n"})
    (repo / "src" / "app.py").write_text("v4-uncommitted\n")
    gcloud = Gcloud()
    outcome, told = deploy(repo, gcloud)
    image = f"{ad.REPOSITORY}:{done[:7]}"
    assert outcome == f"deployed {done[:7]}"
    assert gcloud.built["src/app.py"] == "v2\n"
    assert "tasks/doing/101-b.md" not in gcloud.built
    assert gcloud.steps() == [
        "builds submit --tag",
        "run jobs update",
        "run jobs execute",
        "run jobs execute",
        "run services update",
    ]
    assert [c for c in gcloud.calls if c[1:4] == ["run", "services", "update"]][0][5] == f"--image={image}"
    assert f"deployed {done[:7]} 100-a revision=thinkhow-00016-abc" in journal(repo)
    assert told == []


def test_only_the_image_changes_on_the_service_and_the_job(repo: Path) -> None:
    done = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud(running=git(repo, "rev-parse", "--short=7", "HEAD~1"))
    deploy(repo, gcloud)
    updates = [
        c for c in gcloud.calls if c[1:3] in (["run", "services"], ["run", "jobs"]) and c[3] == "update"
    ]
    image = f"--image={ad.REPOSITORY}:{done[:7]}"
    assert [c[4:] for c in updates] == [
        [ad.JOB, image, f"--project={ad.PROJECT}", f"--region={ad.REGION}"],
        [ad.SERVICE, image, f"--project={ad.PROJECT}", f"--region={ad.REGION}"],
    ]


def test_no_deploy_while_a_task_with_uncommitted_code_is_in_doing(repo: Path) -> None:
    older = git(repo, "rev-parse", "--short=7", "HEAD")
    done = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    commit(repo, "board: 101-b → doing", {"tasks/doing/101-b.md": "b\n"})
    (repo / "src" / "app.py").write_text("v3-uncommitted\n")
    gcloud = Gcloud(running=older)
    outcome, _ = deploy(repo, gcloud)
    assert outcome == f"deployed {done[:7]}"
    assert gcloud.built["src/app.py"] == "v2\n"
    assert "tasks/doing/101-b.md" not in gcloud.built


def test_no_deploy_of_a_done_commit_whose_tree_still_holds_a_task_in_doing(repo: Path) -> None:
    commit(repo, "board: 102-owner → doing", {"tasks/doing/102-owner.md": "o\n"})
    commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud()
    outcome, _ = deploy(repo, gcloud)
    assert outcome.startswith("skip") and "tasks/doing/" in outcome
    assert gcloud.calls == []


def test_no_deploy_when_the_image_is_already_this_version(repo: Path) -> None:
    done = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud(running=done[:7])
    assert deploy(repo, gcloud)[0] == f"up to date: {done[:7]}"
    assert gcloud.steps() == []


def test_no_deploy_when_nothing_for_the_image_changed(repo: Path) -> None:
    deployed = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    commit(repo, "board: 415-cleanup → done", {"docs/x.md": "d2\n", "tests/t.py": "t\n"})
    gcloud = Gcloud(running=deployed[:7])
    assert deploy(repo, gcloud)[0].startswith("up to date: nothing for the image changed")
    assert gcloud.steps() == []


def test_no_deploy_when_somebody_writes(repo: Path) -> None:
    commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud(writing=[True])
    outcome, told = deploy(repo, gcloud)
    assert outcome.startswith("later")
    assert gcloud.steps() == [] and told == [] and journal(repo) == ""
    filters = [c[3] for c in gcloud.calls if c[1:3] == ["logging", "read"]]
    assert filters and 'httpRequest.requestUrl=~"/reply"' in filters[0]
    assert all("--freshness=15m" in c for c in gcloud.calls if c[1:3] == ["logging", "read"])


def test_no_update_when_somebody_started_writing_during_the_build(repo: Path) -> None:
    commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud(writing=[False, True])
    assert deploy(repo, gcloud)[0].startswith("later")
    assert gcloud.steps() == ["builds submit --tag"]


def test_a_failure_tells_the_owner_rolls_nothing_back_and_is_not_retried(repo: Path) -> None:
    done = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud(running="0000000", fail="services update")
    outcome, told = deploy(repo, gcloud)
    assert outcome == f"failed {done[:7]}: service"
    assert told and told[0][:2] == (done[:7], "100-a") and "ERROR: boom" in told[0][2]
    assert f"failed {done[:7]} 100-a service" in journal(repo)
    assert gcloud.steps()[-1] == "run services update"  # nothing after the failed step: no rollback
    again = Gcloud(running="0000000")
    assert deploy(repo, again)[0].startswith("skip") and again.steps() == []
    assert deploy(repo, again, retry=True)[0] == f"deployed {done[:7]}"


def test_a_failure_of_the_build_updates_nothing(repo: Path) -> None:
    commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    gcloud = Gcloud(fail="builds submit")
    outcome, told = deploy(repo, gcloud)
    assert outcome.endswith(": build") and told
    assert gcloud.steps() == ["builds submit --tag"]


def test_changed_cards_run_the_job_command_between_job_and_service(repo: Path) -> None:
    deployed = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    commit(repo, "board: 302-cards → done", {"cards/b.yaml": "b\n"})
    gcloud = Gcloud(running=deployed[:7])
    deploy(repo, gcloud)
    runs = [
        " ".join(c[1:5]) + " " + next(a for a in c if a.startswith("--args="))
        if "execute" in c
        else " ".join(c[1:4])
        for c in gcloud.calls
        if c[1] == "run" and "describe" not in c
    ]
    assert runs == [
        "run jobs update",
        "run jobs execute thinkhow-learning --args=-m,thinkhow.learning.job,cards",
        "run services update",
    ]
    assert all("seed" not in " ".join(c) for c in gcloud.calls)


def test_code_only_change_runs_no_job_command(repo: Path) -> None:
    deployed = commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    commit(repo, "board: 101-b → done", {"src/app.py": "v3\n"})
    gcloud = Gcloud(running=deployed[:7])
    deploy(repo, gcloud)
    assert gcloud.steps() == ["builds submit --tag", "run jobs update", "run services update"]
    assert (
        "deployed" in journal(repo)
        and "101-b" in journal(repo)
        and "100-a" not in journal(repo).split("deployed")[1]
    )


def test_the_stop_file_turns_it_off(repo: Path) -> None:
    commit(repo, "board: 100-a → done", {"src/app.py": "v2\n"})
    (repo.parent / "state").mkdir()
    (repo.parent / "state" / "off").touch()
    gcloud = Gcloud()
    assert deploy(repo, gcloud)[0].startswith("off") and gcloud.calls == []


def test_the_board_question_lands_in_blocked(repo: Path) -> None:
    for column in ("todo", "doing", "blocked", "done", "proposed"):
        (repo / "tasks" / column).mkdir(parents=True, exist_ok=True)
    notify = ad.board_question(repo)
    notify("abc1234", "100-a", "service: exit 1\nERROR: boom")
    notify("abc1234", "100-a", "service: exit 1\nERROR: boom")
    blocked = list((repo / "tasks" / "blocked").glob("*.md"))
    assert len(blocked) == 1
    text = blocked[0].read_text()
    assert "abc1234" in text and "ERROR: boom" in text and "Відповідь:" in text


def test_image_paths_are_what_the_dockerfile_copies() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    copied = {
        src.rstrip("/")
        for line in re.findall(r"^COPY (?!--from)(.+)$", dockerfile, re.M)
        for src in line.split()[:-1]
    }
    assert copied | {"Dockerfile"} == set(ad.IMAGE_PATHS)


def test_the_cron_line_of_the_doc_runs_a_python_that_meets_requires_python() -> None:
    doc = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")
    (line,) = re.findall(r"echo '(\*/5 [^']+)'", doc)
    cron = re.search(r"PATH=(\S+) (\S+) /home/lao/projects/thinkhow/scripts/auto_deploy\.py", line)
    required = re.search(r'requires-python = ">=(\d+)\.(\d+)"', (ROOT / "pyproject.toml").read_text())
    assert cron and required
    found = shutil.which(cron[2], path=cron[1])
    assert found, cron.groups()
    version = subprocess.run(
        [found, "-c", "import sys; print(*sys.version_info[:2])"], capture_output=True, text=True, check=True
    ).stdout.split()
    assert tuple(map(int, version)) >= tuple(map(int, required.groups())), (found, version)
