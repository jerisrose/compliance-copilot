"""Milestone 2, part 1: fuzzy name screening against the SDN list.

Usage (run copilot.ingest first, so data/processed/sdn.jsonl exists):
    python -m copilot.screen "Jon Doe"
    python -m copilot.screen "Example Trading Co" --threshold 70 --limit 5

Real names on watchlists rarely match exactly: spellings differ, word order
changes ("DOE, Jonathan" vs "Jonathan Doe"), and middle names come and go.
So instead of an exact lookup, we give every listed name a similarity score
from 0 to 100 and return the ones above a threshold.

This step is cheap and fast. It deliberately casts a wide net; in part 2 an
LLM will review each candidate and explain whether it is a true match.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

# rapidfuzz is a third-party library (listed in requirements.txt) for
# fast fuzzy string matching.
#   fuzz.ratio             - how alike two strings are, 0-100.
#   utils.default_process  - lowercases and strips punctuation, so
#                            "DOE, JON" and "doe jon" look alike.
#   process.extract        - scores one query against many names at once.
from rapidfuzz import fuzz, process, utils

from copilot.ingest import SdnEntry

DEFAULT_DATA = Path("data/processed/sdn.jsonl")

# Scores at or above this count as possible matches. Lower it to catch more
# variants (and more false alarms); raise it for fewer, closer matches.
# Choosing this number well is a real compliance decision; milestone 5 will
# measure it against labeled test cases.
DEFAULT_THRESHOLD = 80
DEFAULT_LIMIT = 10

# Every word in the query must match some word in the listed name at least
# this well. Without this rule, "David Tom" matched "MICHIELSEN, Tom" just
# because both contain "Tom".
MIN_WORD_SCORE = 75

# A short word that is the start of a longer one ("Jon" / "Jonathan",
# "Co" / "Company") counts as a strong match.
PREFIX_SCORE = 90


def _word_score(a: str, b: str) -> float:
    """How alike two single words are, 0-100."""
    if a == b:
        return 100.0
    # sorted(..., key=len) puts the shorter word first.
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 2 and long_.startswith(short):
        return max(PREFIX_SCORE, fuzz.ratio(a, b))
    return fuzz.ratio(a, b)


def name_score(query: str, name: str, **kwargs) -> float:
    """Score how well a listed name matches the query, 0-100.

    For each word in the query, find its best-matching word in the name.
    If any query word has no good partner, the name is not a match.
    Otherwise the score is the average of the word scores.

    Word order does not matter, and extra words in the listed name
    (middle names, "LLC") do not count against it.

    (**kwargs accepts extra named options that rapidfuzz passes in and we
    don't use, a bit like an unused varargs parameter in Java.)
    """
    query_words = utils.default_process(query).split()
    name_words = utils.default_process(name).split()
    if not query_words or not name_words:
        return 0.0

    best = [max(_word_score(q, n) for n in name_words) for q in query_words]
    if min(best) < MIN_WORD_SCORE:
        return min(best)
    return sum(best) / len(best)


@dataclass
class Match:
    """One possible match: the listed entry and how similar its name is."""
    entry: SdnEntry
    score: float  # 0-100, higher is closer
    # Which of the entry's names scored best: its main name or one of its
    # aliases. Defaults to "" so existing code that builds a Match still works.
    matched_name: str = ""

    @property
    def via_alias(self) -> bool:
        """True if the best-scoring name was an alias, not the main name.

        @property lets you read this like a field (m.via_alias) even though
        it is calculated, like a Java getter without the brackets.
        """
        return bool(self.matched_name) and self.matched_name != self.entry.name


def load_entries(path: Path = DEFAULT_DATA) -> list[SdnEntry]:
    """Read the JSONL file written by copilot.ingest back into records."""
    entries: list[SdnEntry] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                # json.loads turns the text into a dictionary; the ** spreads
                # its keys into named arguments: SdnEntry(ent_num=..., ...).
                entries.append(SdnEntry(**json.loads(line)))
    return entries


def screen(
    query: str,
    entries: list[SdnEntry],
    threshold: float = DEFAULT_THRESHOLD,
    limit: int = DEFAULT_LIMIT,
) -> list[Match]:
    """Return the closest listed names to the query, best first."""
    if not query.strip():
        return []

    # Build one flat list of every name to check: each entry's main name and
    # all its aliases. "owners" records which entry each name belongs to, at
    # the same position, so owners[i] is the entry for names[i].
    names: list[str] = []
    owners: list[int] = []
    for i, entry in enumerate(entries):  # enumerate gives (position, item)
        for name in [entry.name, *entry.aliases]:  # * unpacks the alias list
            names.append(name)
            owners.append(i)

    # extract returns (matched_name, score, position) tuples, best first.
    # limit=None means "return every name above the threshold": we need them
    # all, because one entry can appear several times (once per alias).
    results = process.extract(
        query,
        names,
        scorer=name_score,  # our own scorer, defined above
        processor=None,     # name_score does its own cleanup
        score_cutoff=threshold,
        limit=None,
    )

    # Keep only the best-scoring name for each entry. Results are sorted best
    # first, so the first time we see an entry is its best name; skip the rest.
    matches: list[Match] = []
    seen: set[int] = set()  # a set is like Java's HashSet
    for matched_name, score, position in results:
        owner = owners[position]
        if owner in seen:
            continue
        seen.add(owner)
        matches.append(Match(entries[owner], score, matched_name))
        if len(matches) == limit:
            break
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen a name against the SDN list")
    parser.add_argument("name", help="the name to screen, in quotes")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"{data_path} not found. Run 'python -m copilot.ingest' first.")
        return

    matches = screen(args.name, load_entries(data_path), args.threshold, args.limit)

    if not matches:
        print(f"No matches at or above {args.threshold} for '{args.name}'.")
        return

    print(f"{len(matches)} possible match(es) for '{args.name}':\n")
    for m in matches:
        programs = ", ".join(m.entry.programs) or "none listed"
        # :5.1f formats the score as a number 5 characters wide with 1 decimal.
        print(f"  {m.score:5.1f}  {m.entry.name}  [{m.entry.sdn_type}; {programs}]")
        if m.via_alias:
            print(f"         matched alias: {m.matched_name}")


if __name__ == "__main__":
    main()
