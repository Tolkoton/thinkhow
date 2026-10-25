"""Disputed (Q2): «2–3 нічиї між новими (`tie-…`, ім'я не закінчується на `-3`)». Read as: new cases (not
in commit 6091f88) with an id starting `tie-` and `kind: tie`, whose `expect` is a new card and whose
`also_ok` or `not_first` names another new card; there are 2 or 3 of them. What counts as a tie «між новими»
is a question to the planner."""

from pc_helpers import NEW_IDS, cases, old_cases


def test_two_or_three_new_tie_cases_between_new_cards() -> None:
    old = {c["id"] for c in old_cases()}
    ties = [
        c["id"]
        for c in cases()
        if c["id"] not in old
        and c["id"].startswith("tie-")
        and c["kind"] == "tie"
        and c["expect"] in NEW_IDS
        and (set(c.get("also_ok", [])) | set(c.get("not_first", []))) & (set(NEW_IDS) - {c["expect"]})
    ]
    assert 2 <= len(ties) <= 3, ties
    assert not any(t.endswith("-3") for t in ties), ties
