"""Test gap (overseer, task 727) of `scripts/smoke_test_learning_loop.py`, step «no question about it again».

S6 of learning-loop (.engine/slices/step-results.md): once the person answered, a later return asks nothing
about the step. The smoke's first check of it looked for «Як він вийшов» only in the text after «Кроки», so a
topic page that asked again with the question placed before the «Кроки» block passed. The check must look
at the whole page: no `.step-question` section anywhere.

The breakage is put in front of the sealed bootstrap (syn_catchup_smoke_run.BOOT): `open_topic` keeps the
question it once showed on every later view that has step results (it asks again), and `topic.html` renders
the question section before the «Кроки» block. The smoke must fail on «no question about it again» alone.
"""

import json
import re
from pathlib import Path

import pytest
import syn_catchup_smoke_run
from syn_catchup_smoke_run import run_smoke

ASKED_BEFORE_STEPS = r"""
import dataclasses as _dc
import json as _json
import os as _os
from pathlib import Path as _Path

import jinja2 as _jinja2
import thinkhow.web.server as _srv
import thinkhow.workspace as _W

_GAP = _Path(_os.environ["SYN_GAP_RECORD"])
_gap = {"asked_again": 0, "pages": []}
_shown = []
_real_open, _real_page = _W.open_topic, _srv._page


def _gap_save():
    _GAP.write_text(_json.dumps(_gap, ensure_ascii=False), encoding="utf-8")


def _open_topic(*args, **kwargs):
    view = _real_open(*args, **kwargs)
    if view.step_question:
        _shown[:] = [view.step_question]
    elif _shown and view.steps:
        _gap["asked_again"] += 1
        view = _dc.replace(view, step_question=_shown[0])
    return view


def _page(request, template, context, name):
    response = _real_page(request, template, context, name)
    if template == "topic.html":
        _gap["pages"].append(response.body.decode("utf-8"))
        _gap_save()
    return response


_source = (_srv.HERE / "templates" / "topic.html").read_text(encoding="utf-8")
_line = next(line for line in _source.splitlines(keepends=True) if "step-question" in line)
_section = _line + "{% endif %}"  # the section's own endif opens the next line
_steps = "{% if view.steps %}"
_moved = _source.replace(_section, "", 1).replace(_steps, _section + "\n" + _steps, 1)
assert _moved != _source and _moved.index("step-question") < _moved.index(_steps)
_srv.TEMPLATES.env.loader = _jinja2.ChoiceLoader(
    [_jinja2.DictLoader({"topic.html": _moved}), _srv.TEMPLATES.env.loader]
)
_W.open_topic, _srv._page = _open_topic, _page
_gap_save()
"""


def test_smoke_fails_when_the_question_comes_again_before_the_steps_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gap = tmp_path / "gap.json"
    monkeypatch.setenv("SYN_GAP_RECORD", str(gap))
    monkeypatch.setattr(syn_catchup_smoke_run, "BOOT", ASKED_BEFORE_STEPS + syn_catchup_smoke_run.BOOT)
    result, _, _ = run_smoke(tmp_path)
    told = json.loads(gap.read_text(encoding="utf-8"))
    assert told["asked_again"] > 0, told
    last = told["pages"][-1]  # the page of the return after the answer
    assert "Кроки" in last and "Як він вийшов" in last, last
    assert "Як він вийшов" not in last.split("Кроки", 1)[-1], "the breakage must be what the old check missed"
    assert result.returncode != 0, result.stdout + result.stderr
    failed = re.findall(r"^FAIL (.*)$", result.stdout, re.MULTILINE)
    assert failed == ["no question about it again"], result.stdout
