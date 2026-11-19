"""Run with:  python -m pytest"""
from pathlib import Path

from copilot.ingest import parse_sdn, write_jsonl

SAMPLE = Path(__file__).parent.parent / "data" / "sample" / "sdn_sample.csv"


def load_sample():
    return parse_sdn(SAMPLE.read_text(encoding="utf-8").splitlines())


def test_parses_all_valid_rows():
    assert len(load_sample()) == 3


def test_blank_type_becomes_entity():
    assert load_sample()[0].sdn_type == "entity"


def test_null_marker_is_removed():
    assert load_sample()[2].remarks == ""


def test_multiple_programs_are_split():
    assert load_sample()[1].programs == ["SAMPLE-PROGRAM", "SAMPLE-TWO"]


def test_skips_malformed_rows():
    assert parse_sdn(["", "not,a,valid,row", "\x1a"]) == []


def test_writes_one_json_line_per_entry(tmp_path):
    out = tmp_path / "sdn.jsonl"
    write_jsonl(load_sample(), out)
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3


# --- Aliases -----------------------------------------------------------------

from copilot.ingest import SdnEntry, attach_aliases, parse_alt

ALT_SAMPLE = Path(__file__).parent.parent / "data" / "sample" / "alt_sample.csv"


def load_alt_sample():
    return parse_alt(ALT_SAMPLE.read_text(encoding="utf-8").splitlines())


def test_aliases_are_grouped_by_entry():
    aliases = load_alt_sample()
    assert aliases[900002] == ["DOE, Johnny", "SMITH, Jonathan"]
    assert aliases[900001] == ["EXAMPLE TRADE CO"]


def test_aliases_are_attached_to_their_entries():
    entries = load_sample()
    attach_aliases(entries, load_alt_sample())
    assert entries[1].aliases == ["DOE, Johnny", "SMITH, Jonathan"]
    assert entries[2].aliases == []  # this entry has no aliases


def test_alias_for_unknown_entry_is_ignored():
    entries = load_sample()
    attach_aliases(entries, load_alt_sample())
    every_alias = [a for e in entries for a in e.aliases]
    assert "ALIAS FOR AN ENTRY NOT IN THE SAMPLE" not in every_alias


def test_records_saved_before_aliases_still_load():
    # A record from an older sdn.jsonl, with no "aliases" key.
    old = {"ent_num": 1, "name": "X", "sdn_type": "entity", "programs": [], "remarks": ""}
    assert SdnEntry(**old).aliases == []
