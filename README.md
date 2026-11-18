# Compliance Copilot

An AI assistant for sanctions screening and regulatory Q&A, built on public
data only (the OFAC SDN list and published FinCEN guidance).

**Status:** milestone 2 complete — fuzzy name screening plus AI review of
each possible match.

## Architecture

```mermaid
flowchart TD
    A[OFAC sanctions list] --> C[Ingestion pipeline]
    B[Regulatory guidance] --> C
    C --> D[(Data store: records and embeddings)]
    D --> E[Name screening: fuzzy match + LLM judge]
    D --> F[Regulatory Q&A: retrieval with citations]
    E --> G[Triage agent]
    F --> G
    G --> H[Analyst review]
    G --> I[Evaluation suite]
```

- **Ingestion** downloads and cleans public data into consistent records.
- **Name screening** uses cheap fuzzy matching to find candidates, then an
  LLM reviews each one and explains its decision.
- **Regulatory Q&A** retrieves relevant passages first, so answers are
  grounded in the documents and cite them.
- **Triage agent** combines both to draft a recommended disposition for an alert.
- **Analyst review** keeps a human as the decision-maker.
- **Evaluation suite** scores every change against labeled test cases.

## Roadmap

| Milestone | What | Status |
|---|---|---|
| 1 | Ingest the OFAC SDN list into clean records | ✅ |
| 2 | Name screening: fuzzy matching, then an LLM judges and explains each hit | ✅ |
| 3 | Regulatory Q&A with citations (RAG) | |
| 4 | Alert-triage agent with tool calling | |
| 5 | Evaluation set and accuracy report | |
| 6 | Demo UI and write-up | |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt

python -m pytest                                              # run the tests
python -m copilot.ingest --source data/sample/sdn_sample.csv  # sample data
python -m copilot.ingest                                      # live OFAC list
python -m copilot.screen "Jon Doe"                            # screen a name
python -m copilot.review "Jon Doe" --dob 1970                 # screen + AI review
```

The AI review needs a free Gemini API key from Google AI Studio. Put it in a
file named `.env` in the project folder (this file is git-ignored):

```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash      # optional; any model your key can use
```

Ingestion writes `data/processed/sdn.jsonl`, one JSON record per line.
Screening reads that file and lists the closest names with a 0-100 score.
Options: `--threshold` (default 80) and `--limit` (default 10).

Review screens the name, then asks the model about the top hits (default 3)
and prints a recommendation with reasons. Options: `--dob`, `--country`,
`--max-reviews`.

## Design decisions

- **Two stages.** Cheap fuzzy matching narrows ~19,500 names to a few; the
  model only sees those few, which keeps cost and latency low.
- **The model recommends; a human decides.** Output is one of
  `likely_match`, `needs_review`, `unlikely_match`, with reasons.
- **Retries.** Temporary failures (busy model, rate limit) are retried with
  exponential backoff: 2, 4, then 8 seconds.
- **Fail safe.** Any remaining model error or malformed answer becomes `needs_review`.
  A broken AI can never quietly clear a name.
- **Untrusted input.** Customer details go into the prompt as JSON inside
  tags, and the model is told to treat them as data, not instructions.
- **Swappable provider.** All model calls go through one small interface in
  `copilot/llm.py`, so adding Claude or OpenAI is one new class, and tests
  run against a fake model at no cost.

## Layout

```
copilot/ingest.py     download and parse the SDN list
copilot/screen.py     fuzzy name screening
copilot/llm.py        connection to the AI model (swappable)
copilot/review.py     AI review of each possible match
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
