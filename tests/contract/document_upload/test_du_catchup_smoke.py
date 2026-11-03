"""Catch-up contract tests of document-upload: the smoke script (slice tester).

Written from the contract (.engine/slices/document-upload.md, «Exit criterion», the smoke line, and «Hardest
seams», Seam 4), not from the code of `scripts/smoke_test_document_upload.py`. Each run is the smoke itself
(see `du_catchup_smoke_run`). The clean run is shared by the tests that read it; each «fails when» test breaks
ONE thing the smoke must notice — an answer of the real server, a stored entry, or the page (a script put
first into its <head>) — checks that the breakage really happened, and expects the smoke to fail.
"""

from __future__ import annotations

from du_catchup_smoke_run import (
    CLOUD_413_AS_FRAGMENT_JS,
    HIDE_SIZE_JS,
    MIB_32,
    NO_ARIA_JS,
    OTHER_WORDS,
    Run,
    clean_run,
    run_smoke,
    server_ran,
)


def _fails(run: Run, what: str, *, uploads: bool = True) -> None:
    server_ran(run, uploads=uploads)
    assert not run.ok, f"the smoke passed with {what}\n" + run.out


def _rewritten(run: Run, what: str) -> None:
    assert [r for r in run.kind("rewritten") if r.get("what") == what], (
        f"the breakage ({what}) never happened, so it was not live\n" + run.out
    )


# --- the clean run ------------------------------------------------------------------------------------------


def test_smoke_prints_ok_against_real_uvicorn_in_local_mode_from_real_chromium() -> None:
    run = clean_run()
    assert run.ok, run.out
    server_ran(run)
    assert all(app["local"] for app in run.kind("app")), f"an app outside local mode: {run.kind('app')}"
    assert all(doc["uvicorn"] for doc in run.docs()), "a /document request not served by uvicorn"
    assert all("Chrome" in doc["ua"] for doc in run.docs()), [doc["ua"] for doc in run.docs()]


def test_smoke_takes_a_screenshot_of_the_topic_page_with_attach() -> None:
    run = clean_run()
    server_ran(run)
    shots = run.kind("screenshot")
    assert shots, "the smoke took no screenshot\n" + run.out
    assert any(shot["attach"] for shot in shots), f"no screenshot was taken with #attach on the page: {shots}"


def test_smoke_uploads_resume_pdf_and_resume_docx_through_the_file_input_and_gets_answers() -> None:
    run = clean_run()
    server_ran(run)
    for name in ("resume.pdf", "resume.docx"):
        assert run.beacons_starting(f"chosen-small-{name}"), f"{name} was never chosen on input#document"
        accepted = [d for d in run.docs_named(name) if d["status"] == 200 and d["answered"]]
        assert accepted, f"no /document of {name} answered 200 with `answered`: {run.docs_named(name)}"
        assert all("file" in d["fields"] for d in accepted), [d["fields"] for d in accepted]


def test_smoke_sends_scan_pdf_and_a_topic_over_the_limit_and_the_server_refuses_both() -> None:
    run = clean_run()
    server_ran(run)
    assert [d for d in run.docs_named("scan.pdf") if d["status"] == 422], (
        f"scan.pdf never got the server's 422: {run.docs_named('scan.pdf')}"
    )
    assert [d for d in run.docs() if d["status"] == 413], (
        f"no /document got the server's DocumentTooLarge 413: {run.docs()}"
    )


def test_smoke_covers_the_pages_two_too_large_paths_a_big_buffer_and_page_route() -> None:
    run = clean_run()
    server_ran(run)
    assert run.beacons_starting("chosen-big-"), "no file over 32 MiB was chosen on input#document"
    assert not run.beacons("fetch-big"), "the page sent a file over 32 MiB"
    assert all(d["size"] <= MIB_32 for d in run.docs()), "a /document over 32 MiB reached the server"
    server_413 = len([d for d in run.docs() if d["status"] == 413])
    assert run.beacons("seen-413") > server_413, (
        f"the page saw {run.beacons('seen-413')} answers 413 of /document and the server sent {server_413}: "
        "no 413 came from page.route"
    )


# --- the smoke's own checks: one breakage at a time -------------------------------------------------------


def test_smoke_fails_when_the_pdf_upload_is_refused() -> None:
    run = run_smoke({"deny": "resume.pdf", "html": OTHER_WORDS})
    _rewritten(run, "deny resume.pdf")
    _fails(run, "every /document of resume.pdf answered 500 before the app saw it (no turn, no answer)")


def test_smoke_fails_when_the_docx_upload_is_refused() -> None:
    run = run_smoke({"deny": "resume.docx", "html": OTHER_WORDS})
    _rewritten(run, "deny resume.docx")
    _fails(run, "every /document of resume.docx answered 500 before the app saw it (no turn, no answer)")


def test_smoke_fails_when_documents_json_does_not_hold_the_docx_text() -> None:
    run = run_smoke({"text_for": "resume.docx", "text": "DUCU: зовсім інший текст"})
    _rewritten(run, "text of resume.docx")
    _fails(run, "the entry of resume.docx in documents.json holding another text")


def test_smoke_fails_when_scan_pdf_shows_other_words_than_err_document_unreadable() -> None:
    run = run_smoke({"on_status": 422, "html": OTHER_WORDS})
    _rewritten(run, "status 422")
    _fails(run, "the server's 422 for scan.pdf carrying a fragment with other words")


def test_smoke_fails_when_the_servers_document_too_large_shows_other_words() -> None:
    run = run_smoke({"on_status": 413, "html": OTHER_WORDS})
    _rewritten(run, "status 413")
    _fails(run, "the server's DocumentTooLarge 413 carrying a fragment with other words")


def test_smoke_fails_when_cloud_runs_413_shows_other_words_than_js_document_too_large() -> None:
    run = run_smoke(breakage=CLOUD_413_AS_FRAGMENT_JS)
    server_ran(run)
    assert run.beacons("cloud413-replaced") > 0, (
        "the page never got a 413 without ThinkHow's fragment, so the breakage was not live\n" + run.out
    )
    _fails(run, "Cloud Run's 413 page reaching the page's code as a fragment with other words")


def test_smoke_fails_when_the_page_sends_a_file_over_32_mib() -> None:
    run = run_smoke(breakage=HIDE_SIZE_JS)
    server_ran(run)
    sent = run.beacons("fetch-big") > 0 or any(d["size"] > MIB_32 for d in run.docs())
    assert run.beacons("size-hidden") > 0 and sent, (
        "the page still refused the file over 32 MiB, so the breakage was not live\n" + run.out
    )
    _fails(run, "the page unable to see the size, sending the file over 32 MiB to /document")


def test_smoke_fails_when_attach_has_no_aria_label() -> None:
    run = run_smoke(breakage=NO_ARIA_JS)
    server_ran(run, uploads=False)  # the page is checked first: the smoke may stop before any upload
    assert run.beacons("aria-removed") > 0, "#attach had no aria-label to take away\n" + run.out
    _fails(run, "#attach without its aria-label", uploads=False)
