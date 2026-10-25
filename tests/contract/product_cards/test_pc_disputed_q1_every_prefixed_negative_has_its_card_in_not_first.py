"""Q1, answered by the planner with the lenient reading (ledger 2026-10-25T22:06:29Z). The line:
«`<префікс>-neg-N` … — `kind: negative` з `not_first: [<нова картка>]` (зокрема на пари меж вище, і хоча б
один hard negative, де нова картка — `expect`, а стара в `not_first`)». A prefixed negative is about the new
card of its prefix: the card stands in its `not_first`, OR it is the case's `expect` (the hard negative, e.g.
`ci-neg-2`: expect customer-interviews, not_first jobs-to-be-done). It is not required to be in `not_first`.
The file keeps its name because the seal state holds this path for Q1."""

from pc_helpers import PREFIX, cases


def test_every_prefixed_negative_names_its_new_card_in_not_first_or_as_expect() -> None:
    by_id = {c["id"]: c for c in cases()}
    for prefix, cid in PREFIX.items():
        negs = [k for k in by_id if k.startswith(f"{prefix}-neg-")]
        assert negs, f"no {prefix}-neg-N"
        for k in negs:
            case = by_id[k]
            assert cid in case.get("not_first", []) or case.get("expect") == cid, (k, cid)
