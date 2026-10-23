"""Helpers for the voice-reply-language contract tests (slice tester). Built from the contract, not the code.

- RULES: the text of `facilitation/rules.md`, by hand (as the sealed skel-facilitation
  test has it).
- RULE_PL / RULE_NONE / rule_with: the two texts of `language_rule` from the contract's «Seam», by hand.
- TABLE: the 85 (code, name) pairs of the S1 language list, as a literal (copied from the
  voice-language fakes); NAMED: «name (code)» for each, as literals.
- ScenarioLlm: a fake `platform.llm.Llm` that records the system instruction of every call.
- ScenarioFacilitate: a `Facilitate` double that records every `FacilitationContext`.
- put_profile / drop_profile: `users/<uid>/profile.json` written or removed past `workspace`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from thinkhow.access import CurrentUser
from thinkhow.facilitation.types import (
    FacilitationContext,
    FacilitatorUpdate,
    MapItem,
    ProblemMap,
    ReplyDelta,
    Turn,
)
from thinkhow.knowledge import Card, CurrentKnowledge, MemoryRecord
from thinkhow.platform import llm as pl
from thinkhow.platform.storage import LocalStorage

PHRASE = "Ніколи не відповідай російською"
HEAD = "# Мова відповіді\n"

RULES = (
    """Ти — фасилітатор ThinkHow: ведеш людину по обраній нею моделі мислення, щоб вона сама дійшла
до ясності. Правила:
- Без готових відповідей. Не кажи людині, що робити, не обирай і не оцінюй варіанти за неї, не давай порад.
"""
    "  Можна віддзеркалити сказане, коротко підсумувати, запропонувати гіпотезу "
    "як питання, коли картка це дозволяє.\n"
    """  Якщо людина просить прямо сказати, що робити, — тепло поясни, що рішення її, і поверни їй питання.
- Одне питання за раз: у полі reply рівно одне питання до людини.
- Відповідай мовою останньої репліки людини (Знання нижче — українською, це не мова відповіді).
- Веди по фазах картки. current_phase_id — фаза, на якій розмова стоїть після твоєї відповіді;
  phase_exit_met — чи виконано критерій виходу цієї фази; коли виконано — переходь до наступної.
"""
    "- Якщо картку пройдено або вона не підходить — скажи в reply, що час "
    "змінити метод, і спитай людину, як вона хоче продовжити.\n"
    """- map_updates — зміни карти проблеми, які випливають з останньої репліки людини (може бути порожнім).
  id нового пункту — новий, напр. «i3»; update і remove — за наявним id; turn — «t<номер з рамки репліки>».
- Не вигадуй фактів про людину; не став діагнозів."""
)

RULE_PL = (
    "Відповідай мовою людини — Polski (pl-PL): цю мову вона обрала для розмов з ThinkHow, "
    "і це правило важливіше за «мовою останньої репліки» вище. "
    "Іншою мовою — лише якщо людина прямо попросить. "
    "Ніколи не відповідай російською — ні на репліку російською, ні на прохання."
)
RULE_NONE = "Ніколи не відповідай російською: на репліку російською відповідай українською."


def rule_with(name: str) -> str:
    """The contract's text with a language, by hand: RULE_PL with its language put in."""
    return RULE_PL.replace("Polski (pl-PL)", name)


def squash(s: str) -> str:
    """Whitespace collapsed to single spaces (Q1: how the contract's wrapped line is read is disputed)."""
    return re.sub(r"\s+", " ", s).strip()


TABLE: tuple[tuple[str, str], ...] = (
    ("af-ZA", "Afrikaans"),
    ("rup-BG", "Armãneashti"),
    ("az-AZ", "Azərbaycan"),
    ("bs-BA", "Bosanski"),
    ("ca-ES", "Català"),
    ("ceb", "Cebuano"),
    ("cs-CZ", "Čeština"),
    ("da-DK", "Dansk"),
    ("de-DE", "Deutsch"),
    ("et-EE", "Eesti"),
    ("en-AU", "English (Australia)"),
    ("en-IN", "English (India)"),
    ("en-GB", "English (United Kingdom)"),
    ("en-US", "English (United States)"),
    ("es-ES", "Español (España)"),
    ("es-US", "Español (Estados Unidos)"),
    ("es-419", "Español (Latinoamérica)"),
    ("fil-PH", "Filipino"),
    ("fr-CA", "Français (Canada)"),
    ("fr-FR", "Français (France)"),
    ("gl-ES", "Galego"),
    ("ha-NG", "Hausa"),
    ("hr-HR", "Hrvatski"),
    ("id-ID", "Indonesia"),
    ("is-IS", "Íslenska"),
    ("it-IT", "Italiano"),
    ("jv-ID", "Jawa"),
    ("kea-CV", "Kabuverdianu"),
    ("sw-KE", "Kiswahili"),
    ("lv-LV", "Latviešu"),
    ("lt-LT", "Lietuvių"),
    ("ln-CD", "Lingála"),
    ("hu-HU", "Magyar"),
    ("mt-MT", "Malti"),
    ("ms-MY", "Melayu"),
    ("nl-NL", "Nederlands"),
    ("nb-NO", "Norsk bokmål"),
    ("uz-UZ", "O‘zbek"),
    ("pl-PL", "Polski"),
    ("pt-BR", "Português (Brasil)"),
    ("pt-PT", "Português (Portugal)"),
    ("ro-RO", "Română"),
    ("sk-SK", "Slovenčina"),
    ("sl-SI", "Slovenščina"),
    ("fi-FI", "Suomi"),
    ("sv-SE", "Svenska"),
    ("vi-VN", "Tiếng Việt"),
    ("tr-TR", "Türkçe"),
    ("el-GR", "Ελληνικά"),
    ("be-BY", "Беларуская"),
    ("bg-BG", "Български"),
    ("ky-KG", "Кыргызча"),
    ("mk-MK", "Македонски"),
    ("mn-MN", "Монгол"),
    ("sr-RS", "Српски"),
    ("tg-TJ", "Тоҷикӣ"),
    ("uk-UA", "Українська"),
    ("kk-KZ", "Қазақ тілі"),
    ("hy-AM", "Հայերեն"),
    ("he-IL", "עברית"),
    ("ar-EG", "العربية"),
    ("sd-Arab-IN", "سنڌي (ڀارت)"),
    ("fa-IR", "فارسی"),
    ("ne-NP", "नेपाली"),
    ("mr-IN", "मराठी"),
    ("hi-IN", "हिन्दी"),
    ("as-IN", "অসমীয়া"),
    ("bn-BD", "বাংলা (বাংলাদেশ)"),
    ("bn-IN", "বাংলা (ভারত)"),
    ("pa-Guru-IN", "ਪੰਜਾਬੀ (ਗੁਰਮੁਖੀ)"),
    ("pa-IN", "ਪੰਜਾਬੀ (ਭਾਰਤ)"),
    ("gu-IN", "ગુજરાતી"),
    ("or-IN", "ଓଡ଼ିଆ"),
    ("te-IN", "తెలుగు"),
    ("kn-IN", "ಕನ್ನಡ"),
    ("ml-IN", "മലയാളം"),
    ("th-TH", "ไทย"),
    ("my-MM", "မြန်မာ"),
    ("ka-GE", "ქართული"),
    ("ko-KR", "한국어"),
    ("am-ET", "አማርኛ"),
    ("km-KH", "ខ្មែរ"),
    ("cmn-Hans-CN", "中文 (简体)"),
    ("ja-JP", "日本語"),
    ("yue-Hant-HK", "粵語"),
)

T0 = datetime(2026, 10, 23, 16, 0, 0, tzinfo=UTC)
ALICE = CurrentUser(id="alice-1", email="alice@example.com", is_owner=False)


# --- facilitation side --------------------------------------------------------------------------


@dataclass
class LlmCall:
    system: str
    contents: list[pl.Turn]


@dataclass
class ScenarioLlm:
    deltas: list[str] = field(default_factory=list)
    done_raw: str = ""
    generate: list[str] = field(default_factory=list)
    stream_calls: list[LlmCall] = field(default_factory=list)
    generate_calls: list[LlmCall] = field(default_factory=list)

    def stream_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[BaseModel], rev: pl.KnowledgeRev | None
    ) -> Iterator[pl.ReplyDelta | pl.Done]:
        self.stream_calls.append(LlmCall(system, list(contents)))
        return self._stream()

    def _stream(self) -> Iterator[pl.ReplyDelta | pl.Done]:
        for step in self.deltas:
            yield pl.ReplyDelta(text=step)
        yield pl.Done(
            raw_json=self.done_raw, usage=pl.Usage(prompt_tokens=10, output_tokens=5, thought_tokens=0)
        )

    def generate_json(
        self, system: str, contents: Sequence[pl.Turn], schema: type[Any], rev: pl.KnowledgeRev | None
    ) -> Any:
        self.generate_calls.append(LlmCall(system, list(contents)))
        if not self.generate:
            raise AssertionError("generate_json was called more times than the scenario planned")
        return schema.model_validate_json(self.generate.pop(0))


def _phase(pid: str) -> dict[str, Any]:
    return {
        "id": pid,
        "title": f"Фаза {pid}",
        "goal": f"мета {pid}",
        "how": [f"як {pid}"],
        "exit": f"вихід {pid}",
    }


def card(cid: str, phase_ids: Iterable[str]) -> Card:
    return Card.model_validate(
        {
            "id": cid,
            "title": f"Картка {cid}",
            "router": {
                "needs": f"потреба {cid}",
                "when_yes": [f"так {cid}"],
                "when_no": [f"ні {cid}"],
                "signals": [f"сигнал {cid}"],
            },
            "facilitator": {
                "purpose": f"навіщо {cid}",
                "stance": f"позиція {cid}",
                "needs": f"на вході {cid}",
                "phases": [_phase(p) for p in phase_ids],
                "ending": f"кінець {cid}",
                "traps": [{"name": f"пастка {cid}", "text": f"текст пастки {cid}"}],
                "pairs_well": f"пара {cid}",
            },
        }
    )


ALPHA = card("alpha", ["a_one", "a_two"])
BETA = card("beta", ["b_one"])
MEMORY = [
    MemoryRecord(
        id="M-1",
        title="Досвід",
        cards=["alpha"],
        noticed="людина поспішає",
        do="повернути до фази",
        basis="3 сесії.",
    )
]


def knowledge(memory: list[MemoryRecord] | None = None) -> CurrentKnowledge:
    return CurrentKnowledge(
        rev=3, n=7, cards={c.id: c for c in (ALPHA, BETA)}, memory=list(MEMORY if memory is None else memory)
    )


def context(language: str | None, card_id: str = "alpha") -> FacilitationContext:
    return FacilitationContext(
        card_id=card_id,
        history=[Turn(role="user", text="Хочу відкрити кав'ярню."), Turn(role="model", text="Який план?")],
        problem_map=ProblemMap(
            items=[MapItem(id="i1", type="plan", text="кав'ярня", turn="t1")], phase_id="a_one", last_turn=1
        ),
        turn_no=3,
        text="За пів року.",
        language=language,
    )


def answer(reply: str, phase: str) -> str:
    return json.dumps(
        {"reply": reply, "current_phase_id": phase, "phase_exit_met": False, "map_updates": []},
        ensure_ascii=False,
    )


def update_only(phase: str) -> str:
    return json.dumps(
        {"current_phase_id": phase, "phase_exit_met": False, "map_updates": []}, ensure_ascii=False
    )


def collect(start: Callable[[], Iterator[Any]]) -> tuple[list[Any], BaseException | None]:
    items: list[Any] = []
    try:
        for item in start():
            items.append(item)
    except NotImplementedError:
        raise
    except Exception as exc:  # the test inspects what ended the stream
        return items, exc
    return items, None


# --- workspace side -----------------------------------------------------------------------------


class LlmUnavailable(Exception):
    """A model failure that leaves the person's turn unanswered (so `retry` has work)."""


Step = str | FacilitatorUpdate | BaseException


@dataclass
class ScenarioFacilitate:
    scripts: list[list[Step]] = field(default_factory=list)
    contexts: list[FacilitationContext] = field(default_factory=list)

    def __call__(self, ctx: FacilitationContext) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        self.contexts.append(ctx)
        if not self.scripts:
            raise AssertionError("facilitate was called more times than the scenario planned")
        return self._run(self.scripts.pop(0))

    def _run(self, script: list[Step]) -> Iterator[ReplyDelta | FacilitatorUpdate]:
        for step in script:
            if isinstance(step, BaseException):
                raise step
            if isinstance(step, FacilitatorUpdate):
                yield step
            else:
                yield ReplyDelta(text=step)


def ok(reply: str = "Що може піти не так?") -> list[Step]:
    return [
        reply,
        FacilitatorUpdate(reply=reply, current_phase_id="p1", phase_exit_met=False, map_updates=[]),
    ]


def fail() -> list[Step]:
    return [LlmUnavailable("down")]


def profile_path(user: CurrentUser) -> str:
    return f"{user.id}/profile.json"


def put_profile(store: LocalStorage, user: CurrentUser, data: bytes) -> None:
    store.write("users", profile_path(user), data, "application/json")


def put_code(store: LocalStorage, user: CurrentUser, code: object) -> None:
    put_profile(store, user, json.dumps({"email": user.email, "language": code}, ensure_ascii=False).encode())


def drop_profile(store: LocalStorage, user: CurrentUser) -> None:
    file = store.root / "users" / profile_path(user)
    if file.exists():
        file.unlink()
    assert store.read("users", profile_path(user)) is None


# What the model must read for each code (Seam: `f"{lang.name} ({lang.code})"`), written out as literals.
NAMED: tuple[tuple[str, str], ...] = (
    ("af-ZA", "Afrikaans (af-ZA)"),
    ("rup-BG", "Armãneashti (rup-BG)"),
    ("az-AZ", "Azərbaycan (az-AZ)"),
    ("bs-BA", "Bosanski (bs-BA)"),
    ("ca-ES", "Català (ca-ES)"),
    ("ceb", "Cebuano (ceb)"),
    ("cs-CZ", "Čeština (cs-CZ)"),
    ("da-DK", "Dansk (da-DK)"),
    ("de-DE", "Deutsch (de-DE)"),
    ("et-EE", "Eesti (et-EE)"),
    ("en-AU", "English (Australia) (en-AU)"),
    ("en-IN", "English (India) (en-IN)"),
    ("en-GB", "English (United Kingdom) (en-GB)"),
    ("en-US", "English (United States) (en-US)"),
    ("es-ES", "Español (España) (es-ES)"),
    ("es-US", "Español (Estados Unidos) (es-US)"),
    ("es-419", "Español (Latinoamérica) (es-419)"),
    ("fil-PH", "Filipino (fil-PH)"),
    ("fr-CA", "Français (Canada) (fr-CA)"),
    ("fr-FR", "Français (France) (fr-FR)"),
    ("gl-ES", "Galego (gl-ES)"),
    ("ha-NG", "Hausa (ha-NG)"),
    ("hr-HR", "Hrvatski (hr-HR)"),
    ("id-ID", "Indonesia (id-ID)"),
    ("is-IS", "Íslenska (is-IS)"),
    ("it-IT", "Italiano (it-IT)"),
    ("jv-ID", "Jawa (jv-ID)"),
    ("kea-CV", "Kabuverdianu (kea-CV)"),
    ("sw-KE", "Kiswahili (sw-KE)"),
    ("lv-LV", "Latviešu (lv-LV)"),
    ("lt-LT", "Lietuvių (lt-LT)"),
    ("ln-CD", "Lingála (ln-CD)"),
    ("hu-HU", "Magyar (hu-HU)"),
    ("mt-MT", "Malti (mt-MT)"),
    ("ms-MY", "Melayu (ms-MY)"),
    ("nl-NL", "Nederlands (nl-NL)"),
    ("nb-NO", "Norsk bokmål (nb-NO)"),
    ("uz-UZ", "O‘zbek (uz-UZ)"),
    ("pl-PL", "Polski (pl-PL)"),
    ("pt-BR", "Português (Brasil) (pt-BR)"),
    ("pt-PT", "Português (Portugal) (pt-PT)"),
    ("ro-RO", "Română (ro-RO)"),
    ("sk-SK", "Slovenčina (sk-SK)"),
    ("sl-SI", "Slovenščina (sl-SI)"),
    ("fi-FI", "Suomi (fi-FI)"),
    ("sv-SE", "Svenska (sv-SE)"),
    ("vi-VN", "Tiếng Việt (vi-VN)"),
    ("tr-TR", "Türkçe (tr-TR)"),
    ("el-GR", "Ελληνικά (el-GR)"),
    ("be-BY", "Беларуская (be-BY)"),
    ("bg-BG", "Български (bg-BG)"),
    ("ky-KG", "Кыргызча (ky-KG)"),
    ("mk-MK", "Македонски (mk-MK)"),
    ("mn-MN", "Монгол (mn-MN)"),
    ("sr-RS", "Српски (sr-RS)"),
    ("tg-TJ", "Тоҷикӣ (tg-TJ)"),
    ("uk-UA", "Українська (uk-UA)"),
    ("kk-KZ", "Қазақ тілі (kk-KZ)"),
    ("hy-AM", "Հայերեն (hy-AM)"),
    ("he-IL", "עברית (he-IL)"),
    ("ar-EG", "العربية (ar-EG)"),
    ("sd-Arab-IN", "سنڌي (ڀارت) (sd-Arab-IN)"),
    ("fa-IR", "فارسی (fa-IR)"),
    ("ne-NP", "नेपाली (ne-NP)"),
    ("mr-IN", "मराठी (mr-IN)"),
    ("hi-IN", "हिन्दी (hi-IN)"),
    ("as-IN", "অসমীয়া (as-IN)"),
    ("bn-BD", "বাংলা (বাংলাদেশ) (bn-BD)"),
    ("bn-IN", "বাংলা (ভারত) (bn-IN)"),
    ("pa-Guru-IN", "ਪੰਜਾਬੀ (ਗੁਰਮੁਖੀ) (pa-Guru-IN)"),
    ("pa-IN", "ਪੰਜਾਬੀ (ਭਾਰਤ) (pa-IN)"),
    ("gu-IN", "ગુજરાતી (gu-IN)"),
    ("or-IN", "ଓଡ଼ିଆ (or-IN)"),
    ("te-IN", "తెలుగు (te-IN)"),
    ("kn-IN", "ಕನ್ನಡ (kn-IN)"),
    ("ml-IN", "മലയാളം (ml-IN)"),
    ("th-TH", "ไทย (th-TH)"),
    ("my-MM", "မြန်မာ (my-MM)"),
    ("ka-GE", "ქართული (ka-GE)"),
    ("ko-KR", "한국어 (ko-KR)"),
    ("am-ET", "አማርኛ (am-ET)"),
    ("km-KH", "ខ្មែរ (km-KH)"),
    ("cmn-Hans-CN", "中文 (简体) (cmn-Hans-CN)"),
    ("ja-JP", "日本語 (ja-JP)"),
    ("yue-Hant-HK", "粵語 (yue-Hant-HK)"),
)
