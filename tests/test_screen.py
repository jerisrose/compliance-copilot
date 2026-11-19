"""Tests for fuzzy name screening. Run with:  python -m pytest"""
from pathlib import Path

from copilot.ingest import SdnEntry, parse_sdn, write_jsonl
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


# Names like those on the real list. These cases come from trying the first
# version on live data, where one shared word ("Tom", "David") was enough to
# score a match.
REALISTIC = [
    SdnEntry(1, "MICHIELSEN, Tom", "individual", [], ""),
    SdnEntry(2, "GOMEZ ORTIZ, David", "individual", [], ""),
    SdnEntry(3, "CABELLO RONDON, Jose David", "individual", [], ""),
    SdnEntry(4, "GIL GARCIA, Jose Alejandro", "individual", [], ""),
    SdnEntry(5, "IBRAHIM, Osama Al Kuni", "individual", [], ""),
    SdnEntry(6, "AYDEN", "vessel", [], ""),
    SdnEntry(7, "BIN LADIN, Usama bin Muhammad bin Awad", "individual", [], ""),
]


def realistic_names(query):
    return [m.entry.name for m in screen(query, REALISTIC)]


def test_one_shared_word_is_not_enough():
    assert realistic_names("David Tom") == []


def test_shared_letters_are_not_enough():
    assert realistic_names("Maria Garcia") == []


def test_full_name_match_only_returns_that_person():
    assert realistic_names("Jose David") == ["CABELLO RONDON, Jose David"]


def test_typo_still_matches():
    assert realistic_names("Jose Davd") == ["CABELLO RONDON, Jose David"]


def test_transliterated_spelling_matches():
    # "Osama Laden" vs the listed "Usama ... Ladin"
    assert realistic_names("Osama Laden") == ["BIN LADIN, Usama bin Muhammad bin Awad"]


def test_alias_finds_entry_the_main_name_would_miss():
    entry = SdnEntry(8, "BIN LADIN, Usama bin Muhammad bin Awad", "individual", [], "",
                     aliases=["BIN LADEN, Osama"])
    matches = screen("Osama bin Laden", [entry])
    assert len(matches) == 1
    assert matches[0].score == 100
    assert matches[0].via_alias
    assert matches[0].matched_name == "BIN LADEN, Osama"


def test_entry_matching_several_aliases_appears_once():
    entry = SdnEntry(9, "EXAMPLE TRADING COMPANY LLC", "entity", [], "",
                     aliases=["EXAMPLE TRADING CO", "EXAMPLE TRADING COMPANY"])
    assert len(screen("Example Trading Company", [entry])) == 1


def test_main_name_match_is_not_reported_as_alias():
    matches = screen("Jose David", REALISTIC)
    assert not matches[0].via_alias


def test_reads_back_what_ingest_wrote(tmp_path):
    out = tmp_path / "sdn.jsonl"
    write_jsonl(sample_entries(), out)
    assert load_entries(out) == sample_entries()
