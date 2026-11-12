"""Helpers for the deep-change-question contract tests (slice tester; from the contract, not the code).

The sealed helpers of deep-research-confirm-first (`dc_fakes`: the model double `DcLlm`, the deep scenario
DQ / INTRO_* / PLAN_*, the workspace side) are reused as they are: their folder is put on `sys.path`.

Written by hand here: a refined research question DQ2 (it does not contain DQ as a substring) and a third
one DQ3, plan answers with or without the new `question` field, and the proposals' texts for DQ2 and DQ3
(intro + blank line + question + one dash line per sub-question — written out, not computed).
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_DC = str(HERE.parent / "deep_confirm")
if _DC not in sys.path:
    sys.path.insert(0, _DC)

dc: Any = importlib.import_module("dc_fakes")  # the sealed deep-research-confirm-first helpers

CHANGE_PREFIX = "[Стан] Людина змінює попередній план"

DQ: str = dc.DQ
DQ2 = "Хто конкурує з консультантами для Mittelstand у Саксонії і як там знайти перших клієнтів?"
DQ3 = "Які програми IHK оплачують консалтинг для Mittelstand і як швидко там платять?"

CHANGE: str = dc.CHANGE
CHANGE_AGAIN = "І додай, як швидко там платять за консалтинг."

_ABSENT = object()


def plan_with(intro: str, questions: Sequence[str], question: Any = _ABSENT) -> str:
    """A raw plan answer; `question` left out of the JSON unless given (None is written as null)."""
    doc: dict[str, Any] = {"intro": intro, "questions": list(questions)}
    if question is not _ABSENT:
        doc["question"] = question
    return json.dumps(doc, ensure_ascii=False)


PROPOSAL_2_DQ2 = (
    "Дослідю конкурентів на ринку консалтингу Mittelstand — близько двох хвилин. Запускати?\n\n"
    "Хто конкурує з консультантами для Mittelstand у Саксонії і як там знайти перших клієнтів?\n"
    "- Хто головні конкуренти в консалтингу для Mittelstand?\n"
    "- Які консалтингові фірми працюють у Саксонії?"
)
PROPOSAL_4_DQ2 = (
    "Дослідю чотири боки ринку консалтингу — близько двох хвилин. Запускати чи змінити?\n\n"
    "Хто конкурує з консультантами для Mittelstand у Саксонії і як там знайти перших клієнтів?\n"
    "- Які програми IHK оплачують консалтинг?\n"
    "- Як швидко Mittelstand платить консультантам?\n"
    "- Чим нові консультанти виграють перших клієнтів?\n"
    "- Скільки консультантів у Саксонії працюють самі?"
)
PROPOSAL_4_DQ3 = (
    "Дослідю чотири боки ринку консалтингу — близько двох хвилин. Запускати чи змінити?\n\n"
    "Які програми IHK оплачують консалтинг для Mittelstand і як швидко там платять?\n"
    "- Які програми IHK оплачують консалтинг?\n"
    "- Як швидко Mittelstand платить консультантам?\n"
    "- Чим нові консультанти виграють перших клієнтів?\n"
    "- Скільки консультантів у Саксонії працюють самі?"
)


def file_of(question: str, intro: str, questions: Sequence[str]) -> dict[str, Any]:
    return {"question": question, "intro": intro, "questions": list(questions)}
