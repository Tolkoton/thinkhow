"""Contract tests of skel-guards-deploy: `docs/deploy.md` against the code and the contract (slice tester).

A "command" is an occurrence of its phrase in the doc: the rest of that line plus every following
line while the previous one ends in `\\`.
A behaviour about a command holds when SOME occurrence of it satisfies it.
"""

import re

from skelgd_files import Command, commands, read_or_fail

DOC = "docs/deploy.md"
CLOUD_VARS = ("THINKHOW_USERS_BUCKET", "THINKHOW_SYSTEM_BUCKET", "THINKHOW_OWNER_EMAIL")


def doc() -> str:
    return read_or_fail(DOC)


def job_commands() -> list[Command]:
    text = doc()
    return commands(text, "gcloud run jobs deploy") + commands(text, "gcloud run jobs create")


def service_commands() -> list[Command]:
    return commands(doc(), "gcloud run deploy thinkhow")


def flag(name: str, value: str) -> re.Pattern[str]:
    return re.compile(rf"{re.escape(name)}[ =]['\"]?{re.escape(value)}(?![\w.-])")


def _the_one(cmds: list[Command], *needles: str) -> Command:
    found = [c for c in cmds if all(n in c.text for n in needles)]
    assert found, f"no command carries {needles}: {[c.text for c in cmds]}"
    return found[0]


def test_job_command_sets_each_cloud_variable_of_load_settings() -> None:
    _the_one(job_commands(), *CLOUD_VARS)


def test_service_command_sets_each_cloud_variable_and_the_iap_audience() -> None:
    _the_one(service_commands(), *CLOUD_VARS, "THINKHOW_IAP_AUDIENCE")


def test_seed_is_executed_before_the_service_is_deployed() -> None:
    seeds = [c for c in commands(doc(), "gcloud run jobs execute") if "seed" in c.text]
    assert seeds, "no `gcloud run jobs execute` with seed"
    deploy = _the_one(service_commands(), *CLOUD_VARS)
    assert seeds[0].line < deploy.line


def test_job_entry_names_and_web_entry_point_are_named() -> None:
    both = doc() + "\n" + read_or_fail("Dockerfile")
    assert "thinkhow.web.app:app" in both
    assert "thinkhow.learning.job" in both
    assert "seed" in both and "analyze" in both


def test_doc_names_the_project_region_and_vertex_location() -> None:
    text = doc()
    assert "pocket-lawyer-431614" in text
    assert "europe-west3" in text
    assert re.search(r"\beu\b", text)


def test_logs_are_routed_to_a_bucket_in_europe_west3() -> None:
    text = doc()
    assert "gcloud logging buckets create" in text
    assert "gcloud logging sinks update _Default" in text
    assert "_Required" in text


def test_storage_buckets_have_object_versioning() -> None:
    assert "versioning" in doc().lower()


def test_two_service_accounts_with_their_roles() -> None:
    text = doc()
    for needle in (
        "thinkhow-web",
        "thinkhow-job",
        "roles/storage.objectAdmin",
        "roles/storage.objectViewer",
        "roles/aiplatform.user",
    ):
        assert needle in text, needle


def test_service_runs_as_thinkhow_web_and_job_as_thinkhow_job() -> None:
    assert any(re.search(r"--service-account[ =]\S*thinkhow-web", c.text) for c in service_commands())
    assert any(re.search(r"--service-account[ =]\S*thinkhow-job", c.text) for c in job_commands())


def test_image_is_built_by_cloud_build() -> None:
    assert "gcloud builds submit" in doc()


def test_job_command_is_thinkhow_learning_with_its_limits_and_default_args() -> None:
    job = _the_one(job_commands(), "thinkhow-learning")
    assert flag("--task-timeout", "3600s").search(job.text), job.text
    assert flag("--max-retries", "0").search(job.text), job.text
    assert re.search(r"--command[ =]['\"]?python\b", job.text), job.text
    assert "-m,thinkhow.learning.job,analyze" in job.text, job.text


def test_seed_run_replaces_the_whole_args_list() -> None:
    seeds = [c for c in commands(doc(), "gcloud run jobs execute") if "seed" in c.text]
    assert any("-m,thinkhow.learning.job,seed" in c.text and "--args" in c.text for c in seeds), seeds


def test_service_command_has_one_instance_long_timeout_and_iap_only() -> None:
    svc = _the_one(service_commands(), *CLOUD_VARS)
    assert flag("--max-instances", "1").search(svc.text), svc.text
    assert flag("--min-instances", "0").search(svc.text), svc.text
    assert re.search(r"--timeout[ =]['\"]?3600s?(?![\w.-])", svc.text), svc.text
    assert re.search(r"--iap(?![\w-])", svc.text), svc.text
    assert "--no-allow-unauthenticated" in svc.text


def test_iap_audience_has_the_cloud_run_form() -> None:
    assert "/projects/<PROJECT_NUMBER>/locations/europe-west3/services/thinkhow" in doc()


def test_iap_access_is_granted_per_person_and_the_iap_agent_may_invoke() -> None:
    text = doc()
    assert "gcloud iap web add-iam-policy-binding" in text
    assert "roles/iap.httpsResourceAccessor" in text
    assert "gcp-sa-iap.iam.gserviceaccount.com" in text
    assert "roles/run.invoker" in text


def test_scheduler_posts_to_the_job_run_url() -> None:
    text = doc()
    assert "gcloud scheduler jobs create http" in text
    assert re.search(
        r"https://run\.googleapis\.com/v2/projects/\S+/locations/europe-west3/jobs/thinkhow-learning:run",
        text,
    )
    assert "--oauth-service-account-email" in text


def test_owner_checklist_names_pr04_pr07_and_ac1() -> None:
    text = doc()
    for needle in ("PR-04", "PR-07", "AC1", "gcloud storage ls", "observations"):
        assert needle in text, needle


def test_local_image_check_is_described_for_the_owner() -> None:
    text = doc()
    assert "docker build" in text
    assert "THINKHOW_LOCAL=true" in text
