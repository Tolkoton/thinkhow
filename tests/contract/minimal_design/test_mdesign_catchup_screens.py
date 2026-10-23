"""Catch-up contract tests of minimal-design: the screenshot script (slice tester).

Written from the contract (.engine/slices/minimal-design.md, «Seam», «Hardest seams» 1-3, «Exit criterion»),
not from the code. Each run is the exit criterion's command into a temporary `--out`; the page's style sheet
is served from a copy with one breakage laid on it (see `mdesign_catchup_run`); the script must fail on it.
A breakage is a CSS rule appended to the real `style.css`, mostly scoped by a media query to the one context
it names, so it does not touch the checks the contract keeps for other contexts.
"""

from __future__ import annotations

from pathlib import Path

from mdesign_catchup_run import NO_CLIP, PHONE, PHONE_360, PHONE_DARK, SCREENS, png, run_script


def _fails(tmp_path: Path, breakage: str | None = None, *, drop_dark: bool = False, what: str) -> None:
    run = run_script(tmp_path, breakage, drop_dark=drop_dark)
    assert run.served > 0, (
        "the broken style.css never reached the browser: the breakage was not live\n" + run.out
    )
    assert run.code != 0, f"the script passed with {what}\n" + run.out[-4000:]


# --- the clean run ------------------------------------------------------------------------------------------


def test_clean_run_passes_and_leaves_the_nine_screenshots_in_out(tmp_path: Path) -> None:
    run = run_script(tmp_path)
    assert run.served > 0, run.out
    assert run.code == 0, run.out[-4000:]
    found = {p.name for p in run.screens.glob("*.png")}
    assert SCREENS <= found, f"missing: {sorted(SCREENS - found)}"
    for name in SCREENS:
        assert png(run.screens / name), name


# --- Seam 1: the dark theme really switches on --------------------------------------------------------------


def test_fails_when_the_dark_block_never_applies(tmp_path: Path) -> None:
    _fails(tmp_path, drop_dark=True, what="the prefers-color-scheme: dark block switched off")


def test_fails_when_the_light_context_is_as_dark_as_the_dark_one(tmp_path: Path) -> None:
    breakage = "html, body { background: #15171b !important; background-color: #15171b !important; }"
    _fails(tmp_path, breakage, what="the same dark background in the light and the dark context")


# --- Seam 2: «відповідь іде» only while a request is in flight ----------------------------------------------


def test_fails_when_pending_is_shown_always(tmp_path: Path) -> None:
    breakage = (
        "html body #pending#pending { display: inline-block !important; visibility: visible !important; }"
    )
    _fails(tmp_path, breakage, what="#pending visible always")


def test_fails_when_pending_is_never_shown(tmp_path: Path) -> None:
    breakage = "html body #pending#pending { display: none !important; }"
    _fails(tmp_path, breakage, what="#pending never visible")


def test_fails_when_hidden_buttons_show_on_the_phone_in_the_dark_theme_only(tmp_path: Path) -> None:
    breakage = (
        PHONE_DARK + " { html body #retry#retry, html body #recognize#recognize "
        "{ display: inline-block !important; visibility: visible !important; } }"
    )
    _fails(tmp_path, breakage, what="#retry and #recognize shown on a fresh page (phone, dark)")


def test_fails_when_retry_never_shows_after_a_network_error(tmp_path: Path) -> None:
    breakage = "html body #retry#retry { display: none !important; }"
    _fails(tmp_path, breakage, what="#retry hidden even after the network error")


def test_fails_when_every_model_turn_gets_the_before_label(tmp_path: Path) -> None:
    breakage = (
        'html body .turn.model.model.model::before { content: "Фасилітатор" !important; '
        "display: block !important; }"
    )
    _fails(tmp_path, breakage, what="::before «Фасилітатор» on every .turn.model, saved ones too")


def test_fails_when_the_empty_live_box_is_visible(tmp_path: Path) -> None:
    breakage = (
        "html body #live#live { display: block !important; min-height: 3rem !important; "
        "padding: 1rem !important; border: 1px solid currentColor !important; }"
    )
    _fails(tmp_path, breakage, what="an empty #live with a visible block")


def test_fails_when_saved_turn_text_loses_pre_wrap(tmp_path: Path) -> None:
    breakage = ".turn .text, html body .turn .text { white-space: normal !important; }"
    _fails(tmp_path, breakage, what="white-space: normal on .turn .text")


def test_fails_when_a_live_model_turn_loses_pre_wrap(tmp_path: Path) -> None:
    breakage = "html body #live .turn.model { white-space: normal !important; }"
    _fails(tmp_path, breakage, what="white-space: normal on #live .turn.model")


# --- Seam 3: the phone --------------------------------------------------------------------------------------


def test_fails_when_the_field_widens_the_page_at_360_only(tmp_path: Path) -> None:
    breakage = PHONE_360 + " { " + NO_CLIP + " textarea { min-width: 600px !important; } }"
    _fails(tmp_path, breakage, what="a 600px textarea at 360px width")


def test_fails_when_the_long_topic_title_widens_the_phone_page(tmp_path: Path) -> None:
    breakage = (
        PHONE
        + " { "
        + NO_CLIP
        + " h1, h1 * { white-space: nowrap !important; overflow-wrap: normal !important; "
        "word-break: keep-all !important; } }"
    )
    _fails(tmp_path, breakage, what="the 60-letter <h1> not wrapping on the phone")


def test_fails_when_the_long_topic_in_the_list_widens_the_phone_page(tmp_path: Path) -> None:
    breakage = (
        PHONE
        + " { "
        + NO_CLIP
        + " li, li * { white-space: nowrap !important; overflow-wrap: normal !important; "
        "word-break: keep-all !important; overflow: visible !important; text-overflow: clip !important; } }"
    )
    _fails(tmp_path, breakage, what="the 60-letter <li> not wrapping on the phone")
