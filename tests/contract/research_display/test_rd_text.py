"""Contract tests of research-display, `web/text.py`: `turn_html` — everything escaped except the links
`[title](http…)` (Seam 4, the filter itself; the page is in test_rd_page.py)
(slice tester; from the contract)."""

from markupsafe import Markup

from thinkhow.web.text import turn_html

A_OPEN = '<a href="https://a.example/rent" rel="noopener noreferrer" target="_blank">'


def test_seam4_a_plain_link_becomes_an_anchor_with_rel_and_target() -> None:
    got = turn_html(
        "Від 15 євро.\n\nДжерела: [Ціни оренди](https://a.example/rent), [Ринок](http://b.example/m)"
    )
    assert isinstance(got, Markup)
    assert str(got) == (
        "Від 15 євро.\n\nДжерела: "
        + A_OPEN
        + "Ціни оренди</a>, "
        + '<a href="http://b.example/m" rel="noopener noreferrer" target="_blank">Ринок</a>'
    )


def test_seam4_script_in_the_text_is_escaped() -> None:
    assert str(turn_html("<script>alert(1)</script> & 'так'")) == (
        "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &#39;так&#39;"
    )


def test_seam4_javascript_link_is_not_a_link() -> None:
    assert str(turn_html("[x](javascript:alert(1))")) == "[x](javascript:alert(1))"


def test_seam4_address_with_a_quote_is_text_escaped() -> None:
    assert str(turn_html('[a](https://e.org/?q="x")')) == "[a](https://e.org/?q=&#34;x&#34;)"


def test_seam4_ampersand_in_the_address_is_escaped_once() -> None:
    assert str(turn_html("[t](https://a.example/?x=1&y=2)")) == (
        '<a href="https://a.example/?x=1&amp;y=2" rel="noopener noreferrer" target="_blank">t</a>'
    )


def test_seam4_title_is_escaped_and_an_empty_title_or_an_address_with_a_space_stays_text() -> None:
    assert str(turn_html("[<b>Звіт</b>](https://a.example/rent)")) == A_OPEN + "&lt;b&gt;Звіт&lt;/b&gt;</a>"
    assert str(turn_html("[](https://a.example/rent)")) == "[](https://a.example/rent)"
    assert str(turn_html("[a](https://a.example/r ent)")) == "[a](https://a.example/r ent)"
    assert str(turn_html("[a](https://a.example/<x>)")) == "[a](https://a.example/&lt;x&gt;)"
