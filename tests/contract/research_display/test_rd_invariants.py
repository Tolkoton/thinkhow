"""Contract tests of research-display: the invariants I1-I3 (slice tester; inputs chosen by hand from each
«Domain», expected values written by hand)."""

import html
import re
import time
from typing import Any

import httpx
from markupsafe import escape
from rd_fakes import GOOGLE, HeadRecorder, RecordingResolve

from thinkhow.platform import llm as pl
from thinkhow.platform.links import resolve_link
from thinkhow.web.text import turn_html

LINK = GOOGLE + "AUZIYQ-I1"
PAGE = "https://www.carwow.de/skoda/octavia"


def test_I1_resolve_link_gives_the_input_or_an_absolute_http_location_and_never_raises() -> None:
    cases: list[tuple[str, Any, str]] = [
        (LINK, (301, PAGE), PAGE),
        (LINK, (302, PAGE), PAGE),
        (LINK, (303, "http://plain.example/x"), "http://plain.example/x"),
        (LINK, (307, PAGE), PAGE),
        (LINK, (308, PAGE), PAGE),
        (GOOGLE, (302, PAGE), PAGE),
        (LINK, (200, PAGE), LINK),
        (LINK, (204, None), LINK),
        (LINK, (300, PAGE), LINK),
        (LINK, (304, PAGE), LINK),
        (LINK, (404, None), LINK),
        (LINK, (500, PAGE), LINK),
        (LINK, (0, PAGE), LINK),
        (LINK, (302, None), LINK),
        (LINK, (302, ""), LINK),
        (LINK, (302, "/skoda/octavia"), LINK),
        (LINK, (302, "skoda/octavia"), LINK),
        (LINK, (302, "//cdn.example/x"), LINK),
        (LINK, (302, "ftp://files.example/x"), LINK),
        (LINK, (302, "javascript:alert(1)"), LINK),
        (LINK, httpx.TimeoutException("timed out"), LINK),
        (LINK, httpx.ConnectError("refused"), LINK),
        (LINK, OSError("network down"), LINK),
        (LINK, ValueError("bad"), LINK),
        (LINK, RuntimeError("boom"), LINK),
        ("https://a.example/rent", (302, PAGE), "https://a.example/rent"),
        ("https://a.example/rent", OSError("never asked"), "https://a.example/rent"),
        ("", (302, PAGE), ""),
        ("не адреса", (302, PAGE), "не адреса"),
    ]
    for url, answer, want in cases:
        assert resolve_link(url, HeadRecorder(answer)) == want, (url, answer)
    # a lawful resolve after one that failed: the same head object, a new answer
    head = HeadRecorder(OSError("down"))
    assert resolve_link(LINK, head) == LINK
    head.answer = (302, PAGE)
    assert resolve_link(LINK, head) == PAGE


def test_I2_resolve_sources_keeps_first_appearance_order_and_each_url_once_with_first_title() -> None:
    S = pl.Source
    g1, g2, g3 = GOOGLE + "a", GOOGLE + "b", GOOGLE + "c"
    p, q = "https://p.example/", "https://q.example/"

    assert pl.resolve_sources([], RecordingResolve({})) == ()
    assert pl.resolve_sources([S("Одне", g1)], RecordingResolve({g1: p})) == (S("Одне", p),)
    # repeats before resolving
    assert pl.resolve_sources(
        [S("A", "https://a.example/"), S("A2", "https://a.example/"), S("B", "https://b.example/")],
        RecordingResolve({}),
    ) == (S("A", "https://a.example/"), S("B", "https://b.example/"))
    # repeats after resolving: two Google links to one page, and one link to an address already in the list
    assert pl.resolve_sources(
        [S("X", g1), S("Y", g2), S("Z", "https://z.example/"), S("W", g3)],
        RecordingResolve({g1: p, g2: p, g3: "https://z.example/"}),
    ) == (S("X", p), S("Z", "https://z.example/"))
    assert pl.resolve_sources([S("X", g1), S("Y", p)], RecordingResolve({g1: p})) == (S("X", p),)

    # a resolve slow for the first address: the order is still the order of the sources
    def slow_first(url: str) -> None:
        if url == g1:
            time.sleep(0.3)

    assert pl.resolve_sources(
        [S("X", g1), S("Y", g2), S("Z", g3)], RecordingResolve({g1: p, g2: q}, before=slow_first)
    ) == (S("X", p), S("Y", q), S("Z", g3))
    # more sources than threads (8), every one kept in order
    many = [S(f"Д{i}", GOOGLE + f"n{i}") for i in range(11)]
    mapping = {GOOGLE + f"n{i}": f"https://n{i}.example/" for i in range(11)}
    assert pl.resolve_sources(many, RecordingResolve(mapping)) == tuple(
        S(f"Д{i}", f"https://n{i}.example/") for i in range(11)
    )


ALLOWED_OPEN = re.compile(r'<a href="(https?://[^"]*)" rel="noopener noreferrer" target="_blank">')


def test_I3_turn_html_has_no_tag_but_the_safe_anchor_and_everything_else_escaped() -> None:
    texts = [
        "",
        "Звичайний текст без нічого.",
        "<script>alert(1)</script>",
        "a < b > c & d \" e ' f",
        "&lt;вже екрановане&gt; &amp;",
        "[x](javascript:alert(1))",
        "[x](JAVASCRIPT:alert(1)) [y](data:text/html,<b>)",
        '[a](https://e.org/?q="x" onmouseover="alert(1))',
        '[a"b](https://a.example/r) і [<i>](http://b.example/<i>)',
        "[a [b](https://a.example/x) ] [[c]](https://c.example/) [d](https://d.example/(e))",
        "[незакрита (https://a.example/x) [ще [одна",
        "[t](https://a.example/?x=1&y=2&amp;z=3)\n\nДжерела: [A](https://a.example/a), [B](http://b.example/b)",
        "[<img src=x onerror=alert(1)>](https://a.example/)",
        '[ok](https://a.example/x)</a><a href="javascript:alert(1)">x</a>',
    ]
    for text in texts:
        out = str(turn_html(text))
        rest = ALLOWED_OPEN.sub("", out).replace("</a>", "")
        assert "<" not in rest and ">" not in rest and '"' not in rest, (text, out)
        assert str(escape(html.unescape(rest))) == rest, (text, out)
        for href in ALLOWED_OPEN.findall(out):
            assert html.unescape(href).startswith(("https://", "http://")), (text, out)
            assert '"' not in html.unescape(href), (text, out)
        assert out.count("<a ") == out.count("</a>") == len(ALLOWED_OPEN.findall(out)), (text, out)
