"""Week 1: load the public OFAC SDN sanctions list into clean JSONL records.

Usage:
    python -m copilot.ingest                       # download the live list
    python -m copilot.ingest --source data/sample/sdn_sample.csv

The SDN CSV has no header row and uses "-0-" for empty values.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

# Published by the US Treasury. If the download fails, check the current
# link on the OFAC "Sanctions List Service" page and pass it with --source.
SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

NULL_MARKER = "-0-"

# Column positions in sdn.csv
COL_ENT_NUM, COL_NAME, COL_TYPE, COL_PROGRAM = 0, 1, 2, 3
COL_REMARKS = 11
MIN_COLUMNS = 12


@dataclass
class SdnEntry:
    ent_num: int
    name: str
    sdn_type: str  # "individual", "vessel", "aircraft" or "entity"
    programs: list[str]
    remarks: str


def _clean(value: str) -> str:
    value = value.strip()
    return "" if value == NULL_MARKER else value


def parse_sdn(lines: Iterable[str]) -> list[SdnEntry]:
    """Turn raw CSV lines into SdnEntry records, skipping malformed rows."""
    entries: list[SdnEntry] = []
    for row in csv.reader(lines):
        if len(row) < MIN_COLUMNS or not row[COL_ENT_NUM].strip().isdigit():
            continue  # blank lines, end-of-file marker, broken rows
        programs = [p.strip() for p in _clean(row[COL_PROGRAM]).split("]") if p.strip()]
        programs = [p.lstrip("[ ").strip() for p in programs]
        entries.append(
            SdnEntry(
                ent_num=int(row[COL_ENT_NUM]),
                name=_clean(row[COL_NAME]),
                sdn_type=_clean(row[COL_TYPE]).lower() or "entity",
                programs=programs,
                remarks=_clean(row[COL_REMARKS]),
            )
        )
    return entries


def read_source(source: str) -> str:
    """Read the list from a URL or a local file path."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    return Path(source).read_text(encoding="utf-8")


def write_jsonl(entries: list[SdnEntry], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the OFAC SDN list")
    parser.add_argument("--source", default=SDN_URL, help="URL or local CSV path")
    parser.add_argument("--out", default="data/processed/sdn.jsonl")
    args = parser.parse_args()

    entries = parse_sdn(io.StringIO(read_source(args.source)))
    write_jsonl(entries, Path(args.out))
    print(f"Wrote {len(entries)} entries to {args.out}")


if __name__ == "__main__":
    main()
