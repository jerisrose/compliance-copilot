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
#   fuzz.WRatio            - a combined scorer that copes with word order,
#                            partial names and small spelling differences.
#   utils.default_process  - lowercases and strips punctuation before
#                            comparing, so "DOE, JON" and "doe jon" look alike.
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


@dataclass
class Match:
    """One possible match: the listed entry and how similar its name is."""
    entry: SdnEntry
    score: float  # 0-100, higher is closer


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

    names = [e.name for e in entries]

    # extract returns a list of (matched_name, score, position) tuples,
    # already sorted best first. score_cutoff drops anything below threshold.
    results = process.extract(
        query,
        names,
        scorer=fuzz.WRatio,
        processor=utils.default_process,
        score_cutoff=threshold,
        limit=limit,
    )
    # Unpack each tuple; "_" means "a value we don't need".
    return [Match(entry=entries[index], score=score) for _, score, index in results]


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


if __name__ == "__main__":
    main()
