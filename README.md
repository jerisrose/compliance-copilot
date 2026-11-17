# Compliance Copilot

An AI assistant for sanctions screening and regulatory Q&A, built on public
data only (the OFAC SDN list and published FinCEN guidance).

**Status:** milestone 1 — ingestion.

## Roadmap

| Week | Milestone |
|---|---|
| 1 | Ingest the OFAC SDN list into clean records ✅ |
| 2 | Name screening: fuzzy matching, then an LLM judges and explains each hit |
| 3 | Regulatory Q&A with citations (RAG) |
| 4 | Alert-triage agent with tool calling |
| 5 | Evaluation set and accuracy report |
| 6 | Demo UI, architecture diagram, write-up |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m pytest                                              # run the tests
python -m copilot.ingest --source data/sample/sdn_sample.csv  # sample data
python -m copilot.ingest                                      # live OFAC list
```

Output goes to `data/processed/sdn.jsonl`, one JSON record per line.

## Layout

```
copilot/ingest.py     download and parse the SDN list
data/sample/          small fictional sample used by the tests
tests/                pytest tests
```

## Python notes for Java developers

| Python here | Java equivalent |
|---|---|
| `.venv` + `requirements.txt` | a per-project Maven dependency set |
| `@dataclass class SdnEntry` | a `record` |
| `python -m pytest` | `mvn test` |
| `python -m copilot.ingest` | running a class with a `main` method |
| `list[str]`, `-> list[SdnEntry]` | generics and return types (hints only, not enforced) |

## Data note

The sample file contains invented entries. The live list is published by the
US Treasury and is not committed to this repo.
