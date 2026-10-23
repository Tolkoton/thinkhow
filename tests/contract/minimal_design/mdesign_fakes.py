"""Helpers for the minimal-design contract tests (slice tester). Built from the contract, not the code.

- make_app: `create_app(Deps(...))` with a local folder and `IapIdentity(verify_fake)`.
- seed_topic / make_pending: topics made through `workspace` itself (answered exchanges; an unanswered turn).
- Dom: a small element tree of a page (html.parser): tag, attrs, parent, children, text.
- parse_css: comments stripped, a tree of rules (`Rule`: prelude, declarations, children)
  and statement at-rules.
- parse_color / contrast: sRGB colours of hex, rgb(), hsl() and a few names; the WCAG 2.x contrast ratio.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import FacilitatorUpdate, ReplyDelta
from thinkhow.platform.config import load_settings
from thinkhow.platform.identity import IapIdentity
from thinkhow.platform.speech import ScriptedSpeech
from thinkhow.platform.storage import LocalStorage
from thinkhow.web.server import Deps, create_app
from thinkhow.workspace import TopicRef, create_topic, reply, set_language

T0 = datetime(2026, 10, 23, 16, 0, 0, tzinfo=UTC)

ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)
BOB = CurrentUser(id="bob_2", email="bob@example.com", is_owner=False)
OWNER = CurrentUser(id="owner-9", email="owner@example.com", is_owner=True)

IAP = "x-goog-iap-jwt-assertion"
TOKENS: dict[str, dict[str, str]] = {
    "tok-alice": {"sub": "accounts.google.com:alice-1", "email": "alice@example.com"},
    "tok-bob": {"sub": "accounts.google.com:bob_2", "email": "bob@example.com"},
    "tok-owner": {"sub": "accounts.google.com:owner-9", "email": "owner@example.com"},
}
H_ALICE = {IAP: "tok-alice"}
H_BOB = {IAP: "tok-bob"}
H_OWNER = {IAP: "tok-owner"}


def verify_fake(token: str, audience: str) -> dict[str, str]:
    if token not in TOKENS:
        raise RuntimeError("bad signature")
    return TOKENS[token]


class Down(Exception):
    """The model fails: the person's turn stays without an answer."""


def _update(text: str) -> FacilitatorUpdate:
    return FacilitatorUpdate(reply=text, current_phase_id="p1", phase_exit_met=False, map_updates=[])


@dataclass
class Scripted:
    scripts: list[list[Any]] = field(default_factory=list)

    def __call__(self, context: Any) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        if not self.scripts:
            raise AssertionError("facilitate was called more times than planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Any]) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            if isinstance(step, FacilitatorUpdate):
                yield step
            else:
                yield ReplyDelta(text=str(step))


@dataclass
class App:
    client: TestClient
    storage: LocalStorage


def make_app(tmp_path: Path) -> App:
    store = LocalStorage(tmp_path / "data")
    settings = load_settings(
        {
            "THINKHOW_LOCAL": "true",
            "THINKHOW_LOCAL_DIR": str(tmp_path),
            "THINKHOW_OWNER_EMAIL": "owner@example.com",
        }
    )
    deps = Deps(
        storage=store,
        identity=IapIdentity("aud-test", verify_fake),
        settings=settings,
        facilitate=Scripted(),
        now=lambda: T0,
        speech=ScriptedSpeech("(локальний режим) розпізнаний текст"),
    )
    client = TestClient(create_app(deps), raise_server_exceptions=False, follow_redirects=False)
    return App(client, store)


def choose_language(store: LocalStorage, *users: CurrentUser, code: str = "uk-UA") -> None:
    for user in users:
        set_language(store, user, code)


def seed_topic(
    store: LocalStorage, user: CurrentUser, title: str, exchanges: tuple[tuple[str, str], ...] = ()
) -> TopicRef:
    ref = TopicRef(user.id, create_topic(store, user, title, T0))
    for ask, answer in exchanges:
        list(reply(store, Scripted([[answer, _update(answer)]]), user, ref, ask, T0))
    return ref


def make_pending(store: LocalStorage, user: CurrentUser, ref: TopicRef, ask: str) -> None:
    list(reply(store, Scripted([[Down("down")]]), user, ref, ask, T0))


def topic_url(ref: TopicRef) -> str:
    return f"/topics/{ref.uid}/{ref.topic_id}"


# --- HTML ----------------------------------------------------------------------------------------


@dataclass
class El:
    tag: str
    attrs: dict[str, str | None]
    parent: El | None
    children: list[El] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)

    def text(self) -> str:
        out = list(self.parts)
        for c in self.children:
            out.append(c.text())
        return "".join(out)

    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def ancestors(self) -> list[El]:
        found: list[El] = []
        p = self.parent
        while p is not None:
            found.append(p)
            p = p.parent
        return found


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Dom(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root = El("#root", {}, None)
        self.all: list[El] = []
        self._stack: list[El] = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        parent = self._stack[-1]
        el = El(tag, dict(attrs), parent)
        parent.children.append(el)
        self.all.append(el)
        if tag not in VOID:
            self._stack.append(el)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        parent = self._stack[-1]
        el = El(tag, dict(attrs), parent)
        parent.children.append(el)
        self.all.append(el)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].parts.append(data)

    def find(self, tag: str | None = None, **attrs: str) -> list[El]:
        return [
            e
            for e in self.all
            if (tag is None or e.tag == tag) and all(e.attrs.get(k) == v for k, v in attrs.items())
        ]

    def by_id(self, el_id: str) -> El:
        found = self.find(id=el_id)
        assert len(found) == 1, f"expected one element with id={el_id!r}, found {len(found)}"
        return found[0]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --- CSS -----------------------------------------------------------------------------------------


@dataclass
class Rule:
    prelude: str
    declarations: list[tuple[str, str, bool]] = field(default_factory=list)  # (prop, value, important)
    children: list[Rule] = field(default_factory=list)
    is_block_at_rule: bool = False
    is_statement: bool = False


NESTING_AT = ("@media", "@supports", "@layer", "@container", "@document", "@scope")


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def _split_top(text: str, sep: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    cur: list[str] = []
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def parse_declarations(body: str) -> list[tuple[str, str, bool]]:
    out: list[tuple[str, str, bool]] = []
    for chunk in _split_top(body, ";"):
        if ":" not in chunk:
            continue
        prop, value = chunk.split(":", 1)
        value = value.strip()
        important = False
        m = re.search(r"!\s*important\s*$", value, flags=re.I)
        if m:
            important = True
            value = value[: m.start()].strip()
        out.append(
            (prop.strip().lower() if not prop.strip().startswith("--") else prop.strip(), value, important)
        )
    return out


def _parse_block(css: str, i: int) -> tuple[list[Rule], int]:
    rules: list[Rule] = []
    start = i
    quote: str | None = None
    while i < len(css):
        ch = css[i]
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
        elif ch == ";":
            prelude = css[start:i].strip()
            if prelude.startswith("@"):
                rules.append(Rule(prelude, is_statement=True))
            start = i + 1
        elif ch == "{":
            prelude = norm(css[start:i])
            if prelude.lower().startswith(NESTING_AT):
                children, i = _parse_block(css, i + 1)
                rules.append(Rule(prelude, children=children, is_block_at_rule=True))
            else:
                depth = 1
                j = i + 1
                q: str | None = None
                while j < len(css) and depth:
                    c = css[j]
                    if q:
                        if c == q:
                            q = None
                    elif c in "\"'":
                        q = c
                    elif c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                    j += 1
                rules.append(Rule(prelude, declarations=parse_declarations(css[i + 1 : j - 1])))
                i = j - 1
            start = i + 1
        elif ch == "}":
            return rules, i
        i += 1
    return rules, i


def parse_css(css: str) -> list[Rule]:
    rules, _ = _parse_block(strip_comments(css), 0)
    return rules


def walk(rules: list[Rule]) -> Iterator[Rule]:
    for r in rules:
        yield r
        yield from walk(r.children)


def selectors(rule: Rule) -> list[str]:
    return [norm(s) for s in _split_top(rule.prelude, ",")]


def is_dark_block(rule: Rule) -> bool:
    return (
        rule.is_block_at_rule
        and rule.prelude.lower().startswith("@media")
        and re.search(r"prefers-color-scheme\s*:\s*dark", rule.prelude, flags=re.I) is not None
    )


# --- colours -------------------------------------------------------------------------------------

# The CSS named colours (CSS Color 4), written out by hand; used to refuse literal colour names.
NAMED_COLORS = frozenset(
    """aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown
    burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue
    darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen
    darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey
    darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite
    forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
    hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue
    lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
    lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime
    limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple
    mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue
    mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid
    palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum
    powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon seagreen seashell
    sienna silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle
    tomato turquoise violet wheat white whitesmoke yellow yellowgreen""".split()
)

# Names a palette might use, with their sRGB values (CSS Color 4).
_NAME_RGB = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "whitesmoke": (245, 245, 245),
    "gainsboro": (220, 220, 220),
    "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211),
    "silver": (192, 192, 192),
    "darkgray": (169, 169, 169),
    "darkgrey": (169, 169, 169),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "dimgray": (105, 105, 105),
    "dimgrey": (105, 105, 105),
    "snow": (255, 250, 250),
    "ivory": (255, 255, 240),
    "navy": (0, 0, 128),
    "red": (255, 0, 0),
}

Rgba = tuple[float, float, float, float]


def _num(token: str, scale: float) -> float:
    token = token.strip()
    if token.endswith("%"):
        return float(token[:-1]) / 100.0 * scale
    return float(token)


def _hsl_to_rgb(h: float, s: float, light: float) -> tuple[float, float, float]:
    h = (h % 360) / 360.0

    def hue(p: float, q: float, t: float) -> float:
        t %= 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        return (light * 255, light * 255, light * 255)
    q = light * (1 + s) if light < 0.5 else light + s - light * s
    p = 2 * light - q
    return (hue(p, q, h + 1 / 3) * 255, hue(p, q, h) * 255, hue(p, q, h - 1 / 3) * 255)


def parse_color(value: str) -> Rgba | None:
    """An sRGB colour with alpha from hex, rgb()/rgba(), hsl()/hsla() or a known name; else None."""
    v = value.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
    m = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", v)
    if m:
        fn, inner = m.group(1), m.group(2)
        inner = inner.replace("/", " / ")
        alpha = 1.0
        if "/" in inner:
            inner, a_part = inner.split("/", 1)
            alpha = _num(a_part, 1.0)
        tokens = [t for t in re.split(r"[\s,]+", inner.strip()) if t]
        if len(tokens) == 4:
            alpha = _num(tokens[3], 1.0)
            tokens = tokens[:3]
        if len(tokens) != 3:
            return None
        if fn.startswith("rgb"):
            r, g, b = (_num(t, 255.0) for t in tokens)
        else:
            hue = float(tokens[0].removesuffix("deg"))
            r, g, b = _hsl_to_rgb(hue, _num(tokens[1], 1.0), _num(tokens[2], 1.0))
        return (r, g, b, alpha)
    if v in _NAME_RGB:
        r, g, b = _NAME_RGB[v]
        return (r, g, b, 1.0)
    return None


def over(fg: Rgba, bg: Rgba) -> Rgba:
    a = fg[3]
    return (
        fg[0] * a + bg[0] * (1 - a),
        fg[1] * a + bg[1] * (1 - a),
        fg[2] * a + bg[2] * (1 - a),
        1.0,
    )


def luminance(c: Rgba) -> float:
    def ch(x: float) -> float:
        x /= 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a: Rgba, b: Rgba) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
