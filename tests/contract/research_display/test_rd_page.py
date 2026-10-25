"""Contract tests of research-display, the topic page through `TestClient` (local): links in the text of a
turn and the Search suggestions in a sandboxed iframe under the model's answer (Seam 4) (slice tester; from
the contract)."""

import re
from pathlib import Path

from rd_fakes import GOOGLE, entry, seed_answered, write_research
from rq_fakes import T0
from skelweb_fakes import ALICE, BOB, H_ALICE, Page, choose_language, make_app

from thinkhow.workspace import TopicRef

REPO = Path(__file__).resolve().parents[3]
LINE = "\n\nДжерела: [Ціни оренди](https://a.example/rent?x=1&y=2), [Ринок](https://b.example/m)"
ASK = "Що краще: <b>оренда</b> чи купівля?"
ANSWER = "Оренда — від 15 євро за метр." + LINE
HTML_A = (
    "<style>.carousel{white-space:nowrap}.chip{color:#1a73e8}</style>\n"
    '<div class="carousel"><a class="chip" href="' + GOOGLE + 'AUZ1?a=1&amp;b=2">оренда офісу Лейпциг</a>'
    "<a class='chip' href=\"" + GOOGLE + 'AUZ2">ціни "2026" &lt;нові&gt;</a></div>'
)
HTML_B = '<div class="carousel"><a class="chip" href="' + GOOGLE + 'AUZ3">кава Лейпциг</a></div>'
BASE = '<base target="_blank">'
SANDBOX = "allow-popups allow-popups-to-escape-sandbox"


def url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


def index_of_article(page: Page, turn: int) -> int:
    found = [i for i, (t, a) in enumerate(page.tags) if t == "article" and a.get("id") == f"t{turn}"]
    assert len(found) == 1, f"no single <article id=t{turn}>"
    return found[0]


def iframes_between(page: Page, start: int, end: int) -> list[dict[str, str | None]]:
    return [a for t, a in page.tags[start:end] if t == "iframe"]


def test_seam4_topic_page_shows_links_and_one_sandboxed_iframe_per_entry_under_its_answer(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    choose_language(app.storage, ALICE)
    ref = seed_answered(app.storage, ALICE, "Оренда", [(ASK, ANSWER), ("Добре.", "Що далі?")], T0)
    write_research(
        app.storage,
        ref,
        [
            entry(
                2,
                HTML_A,
                [("Ціни оренди", "https://a.example/rent?x=1&y=2"), ("Ринок", "https://b.example/m")],
            ),
            entry(4, None),
            entry(2, HTML_B),
            entry(4, ""),
        ],
    )
    r = app.client.get(url(ref), headers=H_ALICE)
    assert r.status_code == 200
    body = r.text
    rent = '<a href="https://a.example/rent?x=1&amp;y=2" rel="noopener noreferrer" target="_blank">'
    assert rent + "Ціни оренди</a>" in body
    assert '<a href="https://b.example/m" rel="noopener noreferrer" target="_blank">Ринок</a>' in body
    assert "&lt;b&gt;оренда&lt;/b&gt;" in body and "<b>оренда</b>" not in body

    page = Page(body)
    t2, t3 = index_of_article(page, 2), index_of_article(page, 3)
    index_of_article(page, 4)
    assert iframes_between(page, 0, t2) == []
    under_t2 = iframes_between(page, t2, t3)
    assert sorted(a.get("srcdoc") or "" for a in under_t2) == sorted([BASE + HTML_A, BASE + HTML_B])
    for a in under_t2:
        assert a.get("class") == "search-suggestions"
        assert a.get("sandbox") == SANDBOX
        assert a.get("title") == "Пошук Google"
    assert iframes_between(page, t3, len(page.tags)) == []
    # the attribute is escaped: Google's HTML never stands raw in the page
    assert HTML_A not in body

    # a topic without research.json: no iframe at all
    plain = seed_answered(app.storage, ALICE, "Без пошуку", [("Привіт.", "Вітаю.")], T0)
    page2 = Page(app.client.get(url(plain), headers=H_ALICE).text)
    assert iframes_between(page2, 0, len(page2.tags)) == []


def test_seam4_a_foreign_topic_with_research_is_still_404(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    choose_language(app.storage, ALICE)
    ref = seed_answered(app.storage, BOB, "Тема Боба", [(ASK, ANSWER)], T0)
    write_research(app.storage, ref, [entry(2, HTML_A)])
    r = app.client.get(url(ref), headers=H_ALICE)
    assert r.status_code == 404
    assert "carousel" not in r.text and "Тема Боба" not in r.text


def test_style_css_gives_the_suggestions_frame_full_width_no_border_64px() -> None:
    css = (REPO / "src/thinkhow/web/static/style.css").read_text(encoding="utf-8")
    m = re.search(r"\.search-suggestions\s*\{([^}]*)\}", css)
    assert m, "no .search-suggestions rule"
    decls = {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in m.group(1).split(";") if d.strip())}
    assert decls == {"width": "100%", "border": "0", "height": "64px"}
