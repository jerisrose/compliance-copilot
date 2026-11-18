"""Tests for fuzzy name screening. Run with:  python -m pytest"""
from pathlib import Path

from copilot.ingest import parse_sdn, write_jsonl
from copilot.screen import load_entries, screen

SAMPLE = Path(__file__).parent.parent / "data" / "sample" / "sdn_sample.csv"


def sample_entries():
    return parse_sdn(SAMPLE.read_text(encoding="utf-8").splitlines())


def top_name(query):
    matches = screen(query, sample_entries())
    return matches[0].entry.name if matches else None


def test_exact_name_matches():
    assert top_name("EXAMPLE TRADING COMPANY LLC") == "EXAMPLE TRADING COMPANY LLC"


def test_word_order_and_punctuation_do_not_matter():
    assert top_name("Jonathan Doe") == "DOE, Jonathan Example"


def test_short_form_of_a_name_still_matches():
    assert top_name("Jon Doe") == "DOE, Jonathan Example"


def test_abbreviated_company_name_matches():
    assert top_name("Example Trading Co") == "EXAMPLE TRADING COMPANY LLC"


def test_unrelated_name_does_not_match():
    assert screen("Maria Garcia", sample_entries()) == []


def test_empty_query_returns_nothing():
    assert screen("   ", sample_entries()) == []


def test_results_are_sorted_best_first():
    matches = screen("Sample", sample_entries(), threshold=0)
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_reads_back_what_ingest_wrote(tmp_path):
    out = tmp_path / "sdn.jsonl"
    write_jsonl(sample_entries(), out)
    assert load_entries(out) == sample_entries()
