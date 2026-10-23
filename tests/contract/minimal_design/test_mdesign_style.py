"""Contract tests of minimal-design: rules `style.css` must contain (slice tester, from the contract)."""

from __future__ import annotations

from pathlib import Path

from mdesign_fakes import H_ALICE, Rule, make_app, norm, parse_css, selectors, walk


def _rules(tmp_path: Path) -> list[Rule]:
    r = make_app(tmp_path).client.get("/static/style.css", headers=H_ALICE)
    assert r.status_code == 200, f"/static/style.css: {r.status_code}"
    return list(walk(parse_css(r.text)))


def _declares(rules: list[Rule], selector: str, prop: str, value: str, important: bool = False) -> bool:
    for rule in rules:
        if selector not in selectors(rule):
            continue
        for p, v, imp in rule.declarations:
            if p == prop and norm(v).lower() == value and (imp or not important):
                return True
    return False


def test_hidden_attribute_rule_is_display_none_important(tmp_path: Path) -> None:
    rules = _rules(tmp_path)
    assert _declares(rules, "[hidden]", "display", "none", important=True), (
        "no `[hidden] { display: none !important; }` in style.css"
    )


def test_turn_text_and_model_turn_keep_white_space_pre_wrap(tmp_path: Path) -> None:
    rules = _rules(tmp_path)
    for selector in (".turn .text", ".turn.model"):
        assert _declares(rules, selector, "white-space", "pre-wrap"), (
            f"no `white-space: pre-wrap` for `{selector}` in style.css"
        )
