"""Invariant tests of minimal-design (slice tester; inputs chosen by hand from each «Domain»)."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx2
from mdesign_fakes import (
    ALICE,
    BOB,
    H_ALICE,
    H_BOB,
    H_OWNER,
    NAMED_COLORS,
    OWNER,
    Dom,
    Rgba,
    Rule,
    choose_language,
    contrast,
    is_dark_block,
    make_app,
    make_pending,
    over,
    parse_color,
    parse_css,
    seed_topic,
    selectors,
    strip_comments,
    topic_url,
    walk,
)

ASK = "Хочу відкрити кав'ярню.\nДругий рядок."
ANS = "Що може піти не так?"

# --- I1 ------------------------------------------------------------------------------------------

RESOURCE_ATTRS = {
    "link": ("href",),
    "script": ("src",),
    "img": ("src", "srcset"),
    "iframe": ("src",),
    "source": ("src", "srcset"),
    "audio": ("src",),
    "video": ("src", "poster"),
    "track": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "input": ("src",),
}


def _foreign(url: str) -> bool:
    u = url.strip().lower()
    return u.startswith(("http://", "https://", "//"))


def _css_targets(css: str) -> list[str]:
    """Every url(…) target and every @import target of a piece of CSS."""
    text = strip_comments(css)
    found = [m.group(2) for m in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", text, flags=re.I)]
    found += [m.group(2) for m in re.finditer(r"@import\s+(['\"])(.*?)\1", text, flags=re.I)]
    return found


def _check_page(label: str, html: str) -> None:
    dom = Dom(html)
    sheets = [
        e
        for e in dom.find("link")
        if "stylesheet" in (e.attrs.get("rel") or "").lower().split()
        and urlparse(e.attrs.get("href") or "").path == "/static/style.css"
        and not urlparse(e.attrs.get("href") or "").netloc
        and not urlparse(e.attrs.get("href") or "").scheme
    ]
    assert sheets, f"{label}: no <link rel=stylesheet href=/static/style.css>"
    for e in dom.all:
        for attr in RESOURCE_ATTRS.get(e.tag, ()):
            for value in re.split(r"\s*,\s*", e.attrs.get(attr) or ""):
                if value:
                    assert not _foreign(value.split()[0]), f"{label}: <{e.tag} {attr}={value!r}>"
        style_attr = e.attrs.get("style")
        if style_attr:
            for target in _css_targets(style_attr):
                assert not _foreign(target), f"{label}: style attribute pulls {target!r}"
    for e in dom.find("style"):
        for target in _css_targets(e.text()):
            assert not _foreign(target), f"{label}: inline <style> pulls {target!r}"


def test_I1_every_rendered_page_links_style_css_and_pulls_nothing_from_another_origin(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    c = app.client
    choose_language(app.storage, ALICE, OWNER)
    alice_ref = seed_topic(app.storage, ALICE, "Кав'ярня біля дому", ((ASK, ANS), ("Ще одне", "Чому?")))
    alice_pending = seed_topic(app.storage, ALICE, "Тема без відповіді")
    make_pending(app.storage, ALICE, alice_pending, "Питання без відповіді")
    choose_language(app.storage, BOB)
    bob_ref = seed_topic(app.storage, BOB, "Тема Боба", ((ASK, ANS),))

    pages: list[tuple[str, httpx2.Response]] = []
    # «Мої теми»: not the owner (with topics), not the owner with no topics, the owner (with «Усі теми»)
    pages.append(("home, not the owner, with topics", c.get("/", headers=H_ALICE)))
    pages.append(("home, Bob (one topic)", c.get("/", headers=H_BOB)))
    pages.append(("home, the owner", c.get("/", headers=H_OWNER)))
    # «Мова»: with a chosen language and without one
    pages.append(("language page, with a language", c.get("/language", headers=H_ALICE)))
    fresh = make_app(tmp_path / "fresh")
    pages.append(("language page, without a language", fresh.client.get("/language", headers=H_ALICE)))
    no_topics = fresh.client.post("/language", data={"code": "pl-PL"}, headers=H_ALICE)
    assert no_topics.status_code == 303
    pages.append(("home, not the owner, no topics", fresh.client.get("/", headers=H_ALICE)))
    # the topic page: own (with the form), own awaiting an answer, foreign (the owner on Bob's)
    pages.append(("own topic page", c.get(topic_url(alice_ref), headers=H_ALICE)))
    pages.append(("own topic awaiting an answer", c.get(topic_url(alice_pending), headers=H_ALICE)))
    pages.append(("foreign topic page (the owner)", c.get(topic_url(bob_ref), headers=H_OWNER)))

    for label, r in pages:
        assert r.status_code == 200, f"{label}: {r.status_code}"
        assert "text/html" in r.headers["content-type"], label
        _check_page(label, r.text)

    # style.css itself: served by the existing /static mount, no @import / url() of another origin
    css = c.get("/static/style.css", headers=H_ALICE)
    assert css.status_code == 200, f"/static/style.css: {css.status_code}"
    for target in _css_targets(css.text):
        assert not _foreign(target), f"style.css pulls {target!r}"


# --- I2 ------------------------------------------------------------------------------------------

LIGHT_REQUIRED = {
    # (text variable, background variable)
    ("--fg", "--bg"),
    ("--fg", "--surface"),
    ("--fg", "--user-bg"),
    ("--fg", "--field-bg"),
    ("--muted", "--bg"),
    ("--muted", "--surface"),
    ("--muted", "--user-bg"),
    ("--error", "--bg"),
    ("--link", "--bg"),
    ("--link", "--surface"),
    ("--link", "--user-bg"),
    ("--primary-fg", "--primary-bg"),
    ("--fg", "--button-bg"),
}

COLOR_PROPS = {
    "color",
    "background",
    "background-color",
    "border-color",
    "outline-color",
    "border",
    "border-top",
    "border-right",
    "border-bottom",
    "border-left",
    "border-block",
    "border-block-start",
    "border-block-end",
    "border-inline",
    "border-inline-start",
    "border-inline-end",
    "outline",
}


def _palette(rules: list[Rule]) -> tuple[dict[str, str], dict[str, str]]:
    light: dict[str, str] = {}
    dark: dict[str, str] = {}
    for r in rules:  # the top level only: the :root rule(s)
        if not r.is_block_at_rule and not r.is_statement and ":root" in selectors(r):
            light.update({p: v for p, v, _ in r.declarations if p.startswith("--")})
    for r in walk(rules):
        if is_dark_block(r):
            for inner in walk(r.children):
                dark.update({p: v for p, v, _ in inner.declarations if p.startswith("--")})
    return light, {**light, **dark}


def _resolve(theme: str, palette: dict[str, str], name: str, seen: tuple[str, ...] = ()) -> Rgba:
    assert name in palette, f"{theme}: {name} is not in the palette"
    assert name not in seen, f"{theme}: a var() cycle through {name}"
    value = palette[name].strip()
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,.*)?\)", value)
    if m:
        return _resolve(theme, palette, m.group(1), (*seen, name))
    color = parse_color(value)
    assert color is not None, f"{theme}: {name}: {value!r} is not a colour this test can read"
    return color


def _outside_palette_blocks(rules: list[Rule]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for r in rules:
        if is_dark_block(r):
            continue
        if r.is_block_at_rule:
            out += _outside_palette_blocks(r.children)
            continue
        if r.is_statement or ":root" in selectors(r):
            continue
        out += [(r.prelude, p, v) for p, v, _ in r.declarations if p in COLOR_PROPS]
    return out


def _literal_colors(value: str) -> list[str]:
    v = re.sub(r"var\((?:[^()]|\([^()]*\))*\)", " ", value)  # var(--x) and var(--x, fallback)
    v = re.sub(r"url\((?:[^()])*\)", " ", v, flags=re.I)
    v = re.sub(r"(['\"]).*?\1", " ", v)
    found = re.findall(r"#[0-9a-fA-F]{3,8}\b", v)
    found += [m.group(0) for m in re.finditer(r"\b(?:rgba?|hsla?)\s*\(", v, flags=re.I)]
    found += [w for w in re.findall(r"[A-Za-z][\w-]*", v) if w.lower() in NAMED_COLORS]
    return found


def test_I2_text_pairs_have_contrast_4_5_in_both_themes_and_colours_come_only_from_the_palette(
    tmp_path: Path,
) -> None:
    # the ratio used here, on pairs whose values are known by hand (WCAG 2.x)
    white, black, grey99 = (255, 255, 255, 1.0), (0, 0, 0, 1.0), (153, 153, 153, 1.0)
    assert round(contrast(black, white), 2) == 21.0
    assert round(contrast(grey99, white), 2) == 2.85  # «спокійний» #999 on #fff fails
    assert round(contrast((118, 118, 118, 1.0), white), 2) == 4.54  # #767676 on #fff just passes

    # the palette check, on declarations whose verdict is known by hand
    assert _literal_colors("#999") == ["#999"]
    assert _literal_colors("1px solid White") == ["White"]
    assert _literal_colors("rgb(10, 10, 10)") and _literal_colors("hsl(0 0% 50%)")
    assert _literal_colors("var(--fg)") == []
    assert _literal_colors("3px solid var(--accent)") == []
    assert _literal_colors("transparent") == [] and _literal_colors("currentColor") == []

    app = make_app(tmp_path)
    r = app.client.get("/static/style.css", headers=H_ALICE)
    assert r.status_code == 200, f"/static/style.css: {r.status_code}"
    rules = parse_css(r.text)
    light, dark = _palette(rules)
    assert light, "no :root palette in style.css"
    assert any(is_dark_block(x) for x in walk(rules)), "no @media (prefers-color-scheme: dark) block"

    failures: list[str] = []
    for theme, palette in (("light", light), ("dark", dark)):
        page_bg = _resolve(theme, palette, "--bg")
        assert page_bg[3] == 1.0, f"{theme}: --bg is not opaque"
        for fg_name, bg_name in sorted(LIGHT_REQUIRED):
            bg = over(_resolve(theme, palette, bg_name), page_bg)
            fg = over(_resolve(theme, palette, fg_name), bg)
            ratio = contrast(fg, bg)
            if ratio < 4.5:
                failures.append(f"{theme}: {fg_name} on {bg_name} = {ratio:.2f}:1")
    assert not failures, "contrast below 4.5:1: " + "; ".join(failures)

    literals = [
        f"{sel} {{ {prop}: {value} }} -> {found}"
        for sel, prop, value in _outside_palette_blocks(rules)
        if (found := _literal_colors(value))
    ]
    assert not literals, "literal colours outside the palette: " + "; ".join(literals)
