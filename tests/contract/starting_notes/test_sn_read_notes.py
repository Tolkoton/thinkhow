"""Contract tests of `knowledge.read_notes` (slice tester; from the contract, not the code)."""

from pathlib import Path

import pytest
from sn_fakes import as_record, facilitator, note_dict, router, write_file

from thinkhow.knowledge import read_notes


def test_read_notes_reads_every_yaml_file_by_name_each_a_list_of_records(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    beta = [router("beta", "alpha"), facilitator("beta")]
    alpha = [facilitator("alpha"), router("alpha")]
    write_file(notes, "beta.yaml", beta)
    write_file(notes, "alpha.yaml", alpha)
    (notes / "README.md").write_text("не yaml: [не список", encoding="utf-8")
    got = read_notes(notes)
    assert got == [as_record(item) for item in alpha + beta]
    assert got[0].audience == "facilitator" and got[1].audience == "router"
    assert got[2].cards == ["beta", "alpha"]


def test_read_notes_refuses_a_file_that_is_not_a_list_naming_the_file(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    write_file(notes, "alpha.yaml", [router("alpha")])
    write_file(notes, "broken-map.yaml", router("beta"))
    with pytest.raises(ValueError) as caught:
        read_notes(notes)
    assert "broken-map.yaml" in str(caught.value)


def test_read_notes_refuses_a_record_off_the_schema_naming_the_file(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    write_file(notes, "alpha.yaml", [router("alpha")])
    bad = note_dict("beta-router", ["beta"], "router")
    del bad["basis"]
    write_file(notes, "off-schema.yaml", [bad])
    with pytest.raises(ValueError) as caught:
        read_notes(notes)
    assert "off-schema.yaml" in str(caught.value)
    wrong_audience = note_dict("gamma-router", ["gamma"], "everyone")
    write_file(tmp_path / "other", "bad-audience.yaml", [wrong_audience])
    with pytest.raises(ValueError) as caught_again:
        read_notes(tmp_path / "other")
    assert "bad-audience.yaml" in str(caught_again.value)


def test_read_notes_refuses_two_records_with_one_id(tmp_path: Path) -> None:
    across = tmp_path / "across"
    write_file(across, "alpha.yaml", [router("alpha")])
    write_file(across, "beta.yaml", [note_dict("alpha-router", ["beta"], "router")])
    with pytest.raises(ValueError):
        read_notes(across)
    within = tmp_path / "within"
    write_file(within, "alpha.yaml", [facilitator("alpha"), facilitator("alpha", noticed="інше")])
    with pytest.raises(ValueError):
        read_notes(within)
