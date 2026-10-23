"""Disputed catch-up test of voice-language (slice tester): question CQ1 — not sealed until it is answered.

CQ1: «регіон чи письмо в дужках — лише коли в переліку кілька кодів однієї мови» — is «перелік» the list of
codes the generator is given (so the rule holds for any list), or only the model's 85? The test takes the
first reading: the rule and the order are the generator's, for whatever list it is given.
"""

from __future__ import annotations

from vl_catchup_gen import generate, pairs


def test_generator_adds_the_region_only_when_the_list_has_several_codes_of_one_language() -> None:
    assert pairs(generate("pl-PL en-US de-DE cs-CZ")) == [
        ("cs-CZ", "Čeština"),
        ("de-DE", "Deutsch"),
        ("en-US", "English"),
        ("pl-PL", "Polski"),
    ]
    assert pairs(generate("en-US pt-PT en-GB")) == [
        ("en-GB", "English (United Kingdom)"),
        ("en-US", "English (United States)"),
        ("pt-PT", "Português"),
    ]
