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
