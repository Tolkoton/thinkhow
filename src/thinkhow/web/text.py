"""The text of a turn as HTML: everything escaped, except the Markdown links `[title](http…)` (S1b).

The links are found in the raw text, so nothing the model or the person wrote can become a tag (I3).
"""

import re

from markupsafe import Markup, escape

LINK = re.compile(r"\[([^\[\]]+)\]\((https?://[^\s()\"<>]+)\)")


def turn_html(text: str) -> Markup:
    """Flow: split the raw text at its links → escape the plain pieces → each link an anchor."""
    parts: list[str] = []
    last = 0
    for match in LINK.finditer(text):
        parts.append(str(escape(text[last : match.start()])))
        parts.append(_anchor(match.group(1), match.group(2)))
        last = match.end()
    parts.append(str(escape(text[last:])))
    return Markup("".join(parts))


def _anchor(title: str, url: str) -> str:
    return f'<a href="{escape(url)}" rel="noopener noreferrer" target="_blank">{escape(title)}</a>'
