"""Catch-up contract tests of voice-language: the generator of the language names (slice tester).

Written from the contract (.engine/slices/voice-language.md, «Seam», `LANGUAGES`), not from the code: the
names are «символ у символ», their source is `languages.tsv`, made by `language_names.py` (CLDR through
Babel; hand-written `rup-BG`, `ka-GE`, `cmn-Hans-CN`; `sd-Arab-IN` a special case; order by the name without
diacritics, `casefold`). Expected values are the contract's table (vl_fakes.TABLE), copied by hand.
"""

from __future__ import annotations

from vl_catchup_gen import TSV, generate, model_codes_without_ru, pairs
from vl_fakes import TABLE


def test_generator_given_the_85_model_codes_prints_the_contract_table_pair_by_pair_in_order() -> None:
    codes = model_codes_without_ru()
    assert len(codes) == 85
    assert pairs(generate(" ".join(codes))) == list(TABLE)


def test_generator_orders_by_name_whatever_the_order_of_the_codes_it_is_given() -> None:
    codes = model_codes_without_ru()
    assert pairs(generate(" ".join(reversed(codes)))) == list(TABLE)


def test_languages_tsv_is_what_the_generator_prints_for_the_85_codes() -> None:
    printed = generate(" ".join(model_codes_without_ru()))
    assert TSV.read_text(encoding="utf-8").splitlines() == printed.splitlines()


def test_languages_tsv_holds_the_contract_table_pair_by_pair_in_order() -> None:
    assert pairs(TSV.read_text(encoding="utf-8")) == list(TABLE)
