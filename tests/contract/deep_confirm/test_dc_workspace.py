"""Contract tests of deep-research-confirm-first through `workspace.reply` / `retry` on `LocalStorage`: the
proposal, the person's next turn (yes, change, no, other), `deep_pending.json` between answers, and the
hardest seams 1–6 (slice tester; from the contract, not the code). Every answer reads the topic through a new
storage object on the same folder: nothing is carried in memory from one answer to the next."""

from collections import Counter
from datetime import timedelta
from pathlib import Path

from dc_fakes import (
    ASK_REPLY,
    CARD_PLAIN,
    CARD_REPLY,
    CHANGE,
    DAY,
    DQ,
    FACT_1,
    FACT_2,
    FILE_1,
    FILE_2,
    FIRST_REPLY_LINE,
    PLAN_1,
    PLAN_RAW_1,
    PLAN_RAW_2,
    PROPOSAL_1,
    PROPOSAL_2,
    QUERIES_1,
    QUESTION_HEAD,
    REPORT,
    SOURCES_1,
    SOURCES_LINE_1,
    STEP,
    STEPS_1,
    T0,
    DcLlm,
    Down,
    Q,
    Scripted,
    Stream,
    again,
    agree_llm,
    card_raw,
    chosen_step,
    consent_raw,
    fa,
    fac,
    is_report,
    new_topic,
    pending_file,
    plain,
    propose_on_router,
    put_pending_raw,
    raw_file,
    recorded,
    router_ask,
    router_deep,
    routing_raw,
    rq,
    say,
    store_at,
)

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import Answered, Delta, Failed, TopicRef, open_topic, reply, retry
from thinkhow.workspace.conversation import normalize

YES = "Так, запускай."
NO = "Ні, не треба."


def fact_texts(tmp_path: Path, ref: TopicRef) -> list[str]:
    items = rq.read_map(store_at(tmp_path), ref)["items"]
    return sorted(i["text"] for i in items if i["type"] == "fact")


def propose_under_card(tmp_path: Path, ref: TopicRef) -> DcLlm:
    llm = DcLlm(streams=[Stream([CARD_REPLY], card_raw(CARD_REPLY, "a_one", DQ))], plans=[PLAN_RAW_1])
    got, _ = say(tmp_path, fac(llm), ref, "Хочу продавати консалтинг. Досліди ринок глибоко.")
    assert got[-1] == Answered(2), got[-1]
    return llm


# ------------------------------------------------------------------ Seam 1


def test_seam1_after_yes_the_searches_are_exactly_the_shown_sub_questions_and_no_plan_is_called(
    tmp_path: Path,
) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    assert pending_file(tmp_path, ref) == {"turn": 2, "pending": FILE_1}
    routing_before = routing_raw(tmp_path, ref)

    llm = agree_llm()
    got, shown = say(tmp_path, fac(llm), ref, YES)
    assert got[-1] == Answered(4), got[-1]
    assert Counter(llm.prompts()) == Counter(PLAN_1)
    assert llm.of("plan") == [] and llm.of("router") == [] and llm.of("stream") == []
    assert len(llm.of("consent")) == 1
    assert is_report(shown, STEPS_1, REPORT + SOURCES_LINE_1)
    assert recorded(tmp_path, ref) == normalize(shown)
    entries = rq.read_research(store_at(tmp_path), ref)
    assert entries is not None and len(entries) == 1
    entry = entries[0]
    assert (entry["turn"], entry["depth"], entry["question"], entry["report"]) == (4, "deep", DQ, REPORT)
    assert entry["sources"] == SOURCES_1 and set(entry["queries"]) == QUERIES_1
    assert fact_texts(tmp_path, ref) == sorted([FACT_1, FACT_2])
    assert routing_raw(tmp_path, ref) == routing_before
    assert pending_file(tmp_path, ref) is None


# ------------------------------------------------------------------ Seam 2


def test_seam2_a_change_shows_a_new_proposal_for_the_same_question_and_replaces_the_file(
    tmp_path: Path,
) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    routing_before = routing_raw(tmp_path, ref)
    llm = DcLlm(consents=[consent_raw("change")], plans=[PLAN_RAW_2])
    got, shown = say(tmp_path, fac(llm), ref, CHANGE)
    assert got[-1] == Answered(4), got[-1]
    assert shown == PROPOSAL_2
    assert recorded(tmp_path, ref) == normalize(PROPOSAL_2)
    assert pending_file(tmp_path, ref) == {"turn": 4, "pending": FILE_2}
    assert llm.of("search") == [] and llm.of("router") == [] and llm.of("report") == []
    frame = llm.of("plan")[0]
    assert CHANGE in frame.text and frame.contents[-1].text.endswith(QUESTION_HEAD + DQ)
    assert routing_raw(tmp_path, ref) == routing_before


def test_seam2_other_drops_the_proposal_and_the_reply_goes_the_usual_way(tmp_path: Path) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    llm = DcLlm(consents=[consent_raw("other")], router=[router_ask()])
    got, shown = say(tmp_path, fac(llm), ref, "А взагалі, як мені вибрати нішу?")
    assert got[-1] == Answered(4), got[-1]
    assert shown == ASK_REPLY
    assert len(llm.of("consent")) == 1 and len(llm.of("router")) == 1
    assert llm.of("plan") == [] and llm.of("search") == []
    assert pending_file(tmp_path, ref) is None


def test_other_does_not_turn_deep_off_a_new_deep_question_gives_a_new_proposal(tmp_path: Path) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    llm = DcLlm(consents=[consent_raw("other")], router=[router_deep()], plans=[PLAN_RAW_2])
    got, shown = say(tmp_path, fac(llm), ref, "Краще досліди конкурентів, це інше питання.")
    assert got[-1] == Answered(4), got[-1]
    assert shown == PROPOSAL_2
    assert pending_file(tmp_path, ref) == {"turn": 4, "pending": FILE_2}
    assert llm.of("search") == []


def test_seam2_a_failed_answer_leaves_the_file_and_retry_reads_the_proposal_again(tmp_path: Path) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    before = raw_file(tmp_path, ref, "deep_pending.json")
    got, _ = say(tmp_path, Scripted([[Down("model down")]]), ref, YES)
    assert isinstance(got[-1], Failed), got[-1]
    assert raw_file(tmp_path, ref, "deep_pending.json") == before

    llm = agree_llm()
    got, _ = again(tmp_path, fac(llm), ref)
    assert got[-1] == Answered(4), got[-1]
    assert Counter(llm.prompts()) == Counter(PLAN_1) and llm.of("plan") == []
    assert pending_file(tmp_path, ref) is None


def test_seam2_a_superseded_answer_does_not_touch_the_file(tmp_path: Path) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    late = reply(LocalStorage(tmp_path), Scripted([plain("Добре, без дослідження.")]), rq.ALICE, ref, YES, T0)
    for event in late:
        if isinstance(event, Delta):
            break
    else:
        raise AssertionError("no delta before the end")
    change = DcLlm(consents=[consent_raw("change")], plans=[PLAN_RAW_2])
    assert list(retry(LocalStorage(tmp_path), fac(change), rq.ALICE, ref, T0))[-1] == Answered(4)
    assert pending_file(tmp_path, ref) == {"turn": 4, "pending": FILE_2}
    assert list(late)[-1] == Failed("Superseded")
    assert pending_file(tmp_path, ref) == {"turn": 4, "pending": FILE_2}


def test_a_corrupt_pending_file_is_a_parse_error_without_recovery(tmp_path: Path) -> None:
    for i, data in enumerate(
        (
            b"not json",
            b'{"turn": 2}',
            b'{"turn": 2, "pending": {"question": "x", "intro": "y", "questions": ["a", "b"]}, "extra": 1}',
        )
    ):
        folder = tmp_path / str(i)
        ref = new_topic(folder)
        put_pending_raw(folder, ref, data)
        llm = DcLlm(router=[router_ask()], consents=[consent_raw("other")])
        try:
            got, _ = say(folder, fac(llm), ref, YES)
        except (NotImplementedError, AssertionError):
            raise
        except Exception:
            got = []
        assert not any(isinstance(e, Answered) for e in got), got
        assert llm.calls == []
        assert raw_file(folder, ref, "deep_pending.json") == data


# ------------------------------------------------------------------ Seam 3


def test_seam3_the_answer_that_proposes_searches_nothing_and_writes_no_research(tmp_path: Path) -> None:
    for folder, card in ((tmp_path / "router", None), (tmp_path / "card", "alpha")):
        ref = new_topic(folder, card)
        llm = propose_on_router(folder, ref) if card is None else propose_under_card(folder, ref)
        assert llm.of("search") == [] and llm.of("report") == []
        assert llm.of("consent") == []
        assert len(llm.of("plan")) == 1
        assert rq.raw_research(store_at(folder), ref) is None
        assert pending_file(folder, ref) == {"turn": 2, "pending": FILE_1}


def test_under_the_card_the_proposal_follows_the_card_reply_and_the_card_goes_on(tmp_path: Path) -> None:
    ref = new_topic(tmp_path, "alpha")
    routing_before = routing_raw(tmp_path, ref)
    llm = DcLlm(streams=[Stream([CARD_REPLY], card_raw(CARD_REPLY, "a_one", DQ))], plans=[PLAN_RAW_1])
    got, shown = say(tmp_path, fac(llm), ref, "Хочу продавати консалтинг. Досліди ринок глибоко.")
    assert got[-1] == Answered(2), got[-1]
    assert shown.startswith(CARD_REPLY) and shown.endswith(PROPOSAL_1)
    assert shown[len(CARD_REPLY) : -len(PROPOSAL_1)].strip() == ""
    assert recorded(tmp_path, ref) == normalize(shown)
    assert routing_raw(tmp_path, ref) == routing_before
    assert rq.read_map(store_at(tmp_path), ref)["phase_id"] == "a_one"


# ------------------------------------------------------------------ Seam 4


def test_seam4_no_on_the_router_path_ignores_a_new_deep_question_and_answers_the_fact(tmp_path: Path) -> None:
    ref = new_topic(tmp_path)
    propose_on_router(tmp_path, ref)
    llm = DcLlm(
        consents=[consent_raw("no")],
        router=[router_deep()],
        streams=[Stream(list(fa.DELTAS), fa.fact_raw())],
    )
    got, shown = say(tmp_path, fac(llm), ref, NO)
    assert got[-1] == Answered(4), got[-1]
    assert shown == fa.REPLY
    assert len(llm.of("consent")) == 1 and len(llm.of("router")) == 1 and len(llm.of("stream")) == 1
    assert llm.of("plan") == [] and llm.of("search") == [] and llm.of("report") == []
    assert pending_file(tmp_path, ref) is None


def test_seam4_no_under_the_card_ignores_the_facilitators_new_deep_question(tmp_path: Path) -> None:
    ref = new_topic(tmp_path, "alpha")
    propose_under_card(tmp_path, ref)
    llm = DcLlm(
        consents=[consent_raw("no")], streams=[Stream([CARD_PLAIN], card_raw(CARD_PLAIN, "a_one", DQ))]
    )
    got, shown = say(tmp_path, fac(llm), ref, NO)
    assert got[-1] == Answered(4), got[-1]
    assert shown == CARD_PLAIN
    assert recorded(tmp_path, ref) == CARD_PLAIN
    assert len(llm.of("consent")) == 1
    assert llm.of("plan") == [] and llm.of("search") == [] and llm.of("report") == []
    assert pending_file(tmp_path, ref) is None


def test_yes_under_the_card_runs_the_research_without_ending_the_card_or_moving_the_phase(
    tmp_path: Path,
) -> None:
    ref = new_topic(tmp_path, "alpha")
    propose_under_card(tmp_path, ref)
    routing_before = routing_raw(tmp_path, ref)
    llm = agree_llm()
    got, shown = say(tmp_path, fac(llm), ref, YES)
    assert got[-1] == Answered(4), got[-1]
    assert is_report(shown, STEPS_1, REPORT + SOURCES_LINE_1)
    assert llm.of("stream") == [] and llm.of("router") == [] and llm.of("plan") == []
    assert routing_raw(tmp_path, ref) == routing_before
    assert rq.read_map(store_at(tmp_path), ref)["phase_id"] == "a_one"
    assert fact_texts(tmp_path, ref) == sorted([FACT_1, FACT_2])
    assert pending_file(tmp_path, ref) is None


# ------------------------------------------------------------------ Seam 5


def test_seam5_the_first_reply_line_goes_into_the_plan_frame_only_on_the_router_path_with_no_model_turn(
    tmp_path: Path,
) -> None:
    # a fresh topic, the router's path: the first answer
    ref = new_topic(tmp_path / "a")
    assert FIRST_REPLY_LINE in propose_on_router(tmp_path / "a", ref).of("plan")[0].text

    # the person's first turn failed; a day later turn #2 — still no model turn in the history
    ref = new_topic(tmp_path / "b")
    got, _ = say(tmp_path / "b", Scripted([[Down("model down")]]), ref, "Привіт.")
    assert isinstance(got[-1], Failed)
    assert FIRST_REPLY_LINE in propose_on_router(tmp_path / "b", ref, at=T0 + DAY).of("plan")[0].text

    # the router answered before: not the first answer
    ref = new_topic(tmp_path / "c")
    got, _ = say(tmp_path / "c", fac(DcLlm(router=[router_ask()])), ref, "Привіт.")
    assert got[-1] == Answered(2)
    plan = propose_on_router(tmp_path / "c", ref).of("plan")[0]
    assert FIRST_REPLY_LINE not in plan.text and FIRST_REPLY_LINE not in plan.system

    # under the card the facilitator already says it: the plan frame does not
    ref = new_topic(tmp_path / "d", "alpha")
    plan = propose_under_card(tmp_path / "d", ref).of("plan")[0]
    assert FIRST_REPLY_LINE not in plan.text and FIRST_REPLY_LINE not in plan.system


# ------------------------------------------------------------------ Seam 6


def topic_with_step_and_proposal(tmp_path: Path) -> TopicRef:
    """#1 person, #2 model writes a chosen step; #3 person asks to research deep, #4 the proposal."""
    ref = new_topic(tmp_path)
    got, _ = say(
        tmp_path,
        Scripted([plain("Добре. Що зробите першим кроком?", [chosen_step(2)])]),
        ref,
        "Шукаю клієнтів.",
    )
    assert got[-1] == Answered(2), got[-1]
    propose_on_router(tmp_path, ref)
    assert pending_file(tmp_path, ref) == {"turn": 4, "pending": FILE_1}
    return ref


def step_question_asked(tmp_path: Path, ref: TopicRef) -> bool:
    turns = [t for s in open_topic(store_at(tmp_path), rq.ALICE, ref, T0 + DAY).sessions for t in s.turns]
    return any(t.no == 5 and t.role == "model" and STEP in t.text for t in turns)


def test_seam6_a_step_question_between_the_proposal_and_yes_is_no_consent(tmp_path: Path) -> None:
    ref = topic_with_step_and_proposal(tmp_path)
    llm = DcLlm(router=[router_ask()])
    got, _ = say(tmp_path, fac(llm), ref, "Так.", T0 + DAY, question=Q)
    assert step_question_asked(tmp_path, ref)
    assert got[-1] == Answered(7), got[-1]
    assert llm.of("consent") == [] and llm.of("search") == [] and llm.of("plan") == []
    assert pending_file(tmp_path, ref) is None


def test_seam6_retry_after_a_failure_behind_a_step_question_is_no_consent_either(tmp_path: Path) -> None:
    ref = topic_with_step_and_proposal(tmp_path)
    got, _ = say(tmp_path, Scripted([[Down("model down")]]), ref, "Так.", T0 + DAY, question=Q)
    assert isinstance(got[-1], Failed), got[-1]
    assert step_question_asked(tmp_path, ref)
    assert pending_file(tmp_path, ref) == {"turn": 4, "pending": FILE_1}
    llm = DcLlm(router=[router_ask()])
    got, _ = again(tmp_path, fac(llm), ref, T0 + DAY + timedelta(minutes=1))
    assert got[-1] == Answered(7), got[-1]
    assert llm.of("consent") == [] and llm.of("search") == [] and llm.of("plan") == []
    assert pending_file(tmp_path, ref) is None
