"""Contract tests of voice-language: the list of languages (Seam 4), written from the contract."""

from vl_fakes import GOOGLE_TABLE, TABLE

from thinkhow.workspace import LANGUAGES, Language


def test_seam4_languages_equal_the_contract_table_pair_by_pair_in_order() -> None:
    assert len(TABLE) == 85
    assert [(lang.code, lang.name) for lang in LANGUAGES] == list(TABLE)
    assert all(isinstance(lang, Language) for lang in LANGUAGES)
    codes = [lang.code for lang in LANGUAGES]
    names = [lang.name for lang in LANGUAGES]
    assert len(set(codes)) == 85
    assert len(set(names)) == 85
    assert all(code != "ru-RU" and not code.startswith("ru-") for code in codes)


def test_seam4_language_codes_equal_the_model_table_without_ru_RU() -> None:
    model_codes: set[str] = set()
    for line in GOOGLE_TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        code, _name, _status = (part.strip() for part in line.split("|"))
        model_codes.add(code)
    assert "ru-RU" in model_codes
    assert len(model_codes) == 86
    assert {lang.code for lang in LANGUAGES} == model_codes - {"ru-RU"}
