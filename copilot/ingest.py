"""Milestone 1: load the public OFAC SDN sanctions list into clean JSONL records.

Usage:
    python -m copilot.ingest                       # download the live list
    python -m copilot.ingest --source data/sample/sdn_sample.csv

The SDN CSV has no header row and uses "-0-" for empty values.

(This block in triple quotes is a "docstring": Python's version of a Javadoc
comment. One at the top of a file describes the whole module.)
"""
# Lets us write modern type hints such as list[str] on any Python version.
from __future__ import annotations

# Imports, like Java's. These are all part of Python's standard library,
# so nothing extra needs installing to run this file.
import argparse          # reads command-line options such as --source
import csv               # parses CSV text correctly (quotes, commas in names)
import io                # lets us treat a string as if it were a file
import json              # converts Python objects to JSON text
import urllib.request    # downloads a file from a web address
from dataclasses import asdict, dataclass, field
from pathlib import Path           # an object for file paths, like java.nio.file.Path
from typing import Iterable        # "anything you can loop over", like Java's Iterable

# Constants. Python has no "final" keyword; ALL_CAPS names are the convention
# for "do not change this".

# Published by the US Treasury. If the download fails, check the current
# link on the OFAC "Sanctions List Service" page and pass it with --source.
SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

# The aliases ("also known as" names) are published in a second file.
ALT_URL = "https://www.treasury.gov/ofac/downloads/alt.csv"

# The Treasury file writes "-0-" where a value is empty.
NULL_MARKER = "-0-"

# Column positions in sdn.csv. The file has no header row, so we refer to
# columns by number. Python counts from 0, like Java arrays.
# This line assigns four names at once: COL_ENT_NUM = 0, COL_NAME = 1, ...
COL_ENT_NUM, COL_NAME, COL_TYPE, COL_PROGRAM = 0, 1, 2, 3
COL_REMARKS = 11
MIN_COLUMNS = 12  # a valid row has at least this many columns

# Column positions in alt.csv. Each row is one alias, and its first column
# is the ent_num of the entry it belongs to, like a foreign key in a database.
ALT_COL_ENT_NUM, ALT_COL_NAME = 0, 3
ALT_MIN_COLUMNS = 4


# @dataclass is like a Java record: Python generates the constructor,
# toString and equals for us from the list of fields below.
@dataclass
class SdnEntry:
    ent_num: int          # the Treasury's unique ID for this entry
    name: str             # e.g. "DOE, Jonathan Example"
    sdn_type: str         # "individual", "vessel", "aircraft" or "entity"
    programs: list[str]   # sanctions programs this entry falls under
    remarks: str          # free text: dates of birth, aliases, notes
    # Other names this entry is known by, from the separate aliases file.
    # It has a default (an empty list), so records saved before aliases
    # existed still load. field(default_factory=list) gives each record its
    # own new list; "= []" would share one list between all of them.
    aliases: list[str] = field(default_factory=list)


# A function that stands on its own, outside any class. The leading underscore
# in the name means "private, internal helper" (a convention, not enforced).
# "value: str" and "-> str" are type hints: parameter type and return type.
def _clean(value: str) -> str:
    """Trim spaces and turn the "-0-" marker into an empty string."""
    value = value.strip()  # strip() is Java's trim()
    # A one-line if/else, like Java's ternary:  cond ? "" : value
    return "" if value == NULL_MARKER else value


def parse_sdn(lines: Iterable[str]) -> list[SdnEntry]:
    """Turn raw CSV lines into SdnEntry records, skipping malformed rows."""
    entries: list[SdnEntry] = []  # an empty list, like new ArrayList<SdnEntry>()

    # csv.reader splits each line into a list of column values.
    # Python uses indentation, not curly braces, to mark what is inside the loop.
    for row in csv.reader(lines):
        # Skip anything that is not a real data row: blank lines, the
        # end-of-file marker, or rows where the first column is not a number.
        if len(row) < MIN_COLUMNS or not row[COL_ENT_NUM].strip().isdigit():
            continue

        # The program column looks like "SDGT] [IRAN" when there are several.
        # Split on "]" and tidy each piece to get ["SDGT", "IRAN"].
        # The [ ... for ... if ... ] form is a "list comprehension":
        # Python's compact equivalent of a Java stream with map and filter.
        programs = [p.strip() for p in _clean(row[COL_PROGRAM]).split("]") if p.strip()]
        programs = [p.lstrip("[ ").strip() for p in programs]

        # Build one record and add it to the list. Python has no "new" keyword.
        entries.append(
            SdnEntry(
                ent_num=int(row[COL_ENT_NUM]),
                name=_clean(row[COL_NAME]),
                # Companies have a blank type in the file, so "or" supplies a
                # default: if the left side is empty, use "entity".
                sdn_type=_clean(row[COL_TYPE]).lower() or "entity",
                programs=programs,
                remarks=_clean(row[COL_REMARKS]),
            )
        )
    return entries


def parse_alt(lines: Iterable[str]) -> dict[int, list[str]]:
    """Read the aliases file into {ent_num: [alias, alias, ...]}.

    dict[int, list[str]] is like Java's Map<Integer, List<String>>.
    """
    aliases: dict[int, list[str]] = {}
    for row in csv.reader(lines):
        if len(row) < ALT_MIN_COLUMNS or not row[ALT_COL_ENT_NUM].strip().isdigit():
            continue
        name = _clean(row[ALT_COL_NAME])
        if not name:
            continue
        # setdefault returns the list for this ent_num, creating an empty one
        # the first time; like Java's map.computeIfAbsent(key, k -> new ArrayList<>()).
        aliases.setdefault(int(row[ALT_COL_ENT_NUM]), []).append(name)
    return aliases


def attach_aliases(entries: list[SdnEntry], aliases: dict[int, list[str]]) -> None:
    """Copy each entry's aliases onto it. Changes the entries in place."""
    for entry in entries:
        # .get(key, default) returns the default instead of failing when the
        # key is missing; most entries have no aliases.
        entry.aliases = aliases.get(entry.ent_num, [])


def read_source(source: str) -> str:
    """Read the list from a URL or a local file path, and return its text."""
    # startswith accepts several options at once, given in round brackets.
    if source.startswith(("http://", "https://")):
        # "with" is Python's try-with-resources: the connection is closed
        # automatically when the block ends, even if an error occurs.
        with urllib.request.urlopen(source, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    # Otherwise treat it as a file on disk.
    return Path(source).read_text(encoding="utf-8")


def write_jsonl(entries: list[SdnEntry], out_path: Path) -> None:
    """Write one JSON object per line (the "JSON Lines" format)."""
    # Create the output folder if it does not exist yet.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:  # "w" = open for writing
        for entry in entries:
            # asdict turns the record into a dictionary (like a Java Map),
            # and json.dumps turns that into a line of JSON text.
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def main() -> None:
    """Entry point: read the options, then download, parse and save."""
    # Define the command-line options this program accepts.
    parser = argparse.ArgumentParser(description="Ingest the OFAC SDN list")
    parser.add_argument("--source", default=SDN_URL, help="URL or local CSV path")
    parser.add_argument("--alt-source", default=None,
                        help="URL or local CSV path for aliases (default: live file "
                             "when --source is live, otherwise none)")
    parser.add_argument("--out", default="data/processed/sdn.jsonl")
    args = parser.parse_args()

    # If you gave a local --source but no --alt-source, don't mix a local
    # sample with the live aliases file; just skip aliases.
    alt_source = args.alt_source
    if alt_source is None and args.source == SDN_URL:
        alt_source = ALT_URL

    # The pipeline: read, parse, add aliases, write.
    entries = parse_sdn(io.StringIO(read_source(args.source)))
    alias_count = 0
    if alt_source:
        aliases = parse_alt(io.StringIO(read_source(alt_source)))
        attach_aliases(entries, aliases)
        alias_count = sum(len(e.aliases) for e in entries)
    write_jsonl(entries, Path(args.out))

    # An f-string: values in {curly braces} are inserted into the text,
    # like String.format in Java.
    print(f"Wrote {len(entries)} entries with {alias_count} aliases to {args.out}")


# Python's equivalent of "public static void main". This is true only when the
# file is run directly (python -m copilot.ingest), not when another file
# imports it, which is what the tests do.
if __name__ == "__main__":
    main()
