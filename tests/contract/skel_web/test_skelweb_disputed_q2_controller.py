"""Disputed (Q2): createController of conversation.js under `node --test` (Seam 5). Not sealed until Q2."""

from pathlib import Path

from skelweb_fakes import run_node_test

JS = Path(__file__).parent / "skelweb_disputed_q2_controller.test.mjs"


def test_controller_send_keeps_the_draft_disables_and_posts_to_reply() -> None:
    run_node_test(JS, "controller: send keeps the draft, disables, POSTs to reply")


def test_controller_saved_removes_the_draft_deltas_appended_answered_reloads() -> None:
    run_node_test(JS, "controller: saved removes the draft, deltas appended, answered reloads")


def test_controller_buttons_stay_disabled_until_the_stream_ends() -> None:
    run_node_test(JS, "controller: buttons stay disabled until the stream ends")


def test_controller_failed_shows_retry_and_enables() -> None:
    run_node_test(JS, "controller: failed shows retry and enables")


def test_controller_stream_broken_before_saved_keeps_the_draft() -> None:
    run_node_test(JS, "controller: stream broken before saved keeps the draft")


def test_controller_fetch_rejection_keeps_the_draft() -> None:
    run_node_test(JS, "controller: fetch rejection keeps the draft")


def test_controller_html_error_response_shows_its_text_and_keeps_the_draft() -> None:
    run_node_test(JS, "controller: an HTML error response shows its text and keeps the draft")


def test_controller_stream_closed_after_saved_without_an_end_event() -> None:
    run_node_test(JS, "controller: stream closed after saved without an end event")


def test_controller_stream_closed_before_saved_keeps_the_draft() -> None:
    run_node_test(JS, "controller: stream closed before saved keeps the draft")


def test_controller_retry_posts_to_retry_and_leaves_the_draft_alone() -> None:
    run_node_test(JS, "controller: retry POSTs to retry and leaves the draft alone")


def test_controller_on_open_the_draft_returns_to_the_field() -> None:
    run_node_test(JS, "controller: on open the draft returns to the field")
