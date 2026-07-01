# Signal — an editorial content pipeline

Signal turns a pile of raw industry sources into publish-ready drafts, with
an editor's judgment applied at every stage instead of just at the end.

I built this because the actual bottleneck in small-team editorial
operations is never typing speed — it's triage. Someone still has to read
everything, decide what's a real story versus noise, and shape it into
something readers trust. Signal automates the mechanical parts of that
loop (ingestion, first-pass scoring, drafting, claim-flagging, multi-format
output) so a human editor spends their time on judgment calls, not on
reading fifty press releases to find the one worth writing about.

It's deliberately not a "generate an article" script. It's a pipeline with
an editorial brief at its center, a persistent state store so nothing gets
redrafted or missed, and a clear seam between "what the model proposes"
and "what a human approves" at every stage.

## Why this design

Three decisions shape the whole repo:

1. **Scoring and drafting are separate steps, not one prompt.** A model
   asked to "write about X" will write about X whether or not X is a real
   story. Signal first asks: *is this worth a human's attention, and why?*
   Only stories that clear a configurable bar get drafted. This mirrors
   how an editorial desk actually works — pitch, then assignment, then
   draft — rather than collapsing judgment and execution into one call.

2. **QA is a distinct pass that never touches the prose.** `qa.py`
   extracts factual claims from a draft and flags which ones need a human
   to verify before publish, plus checks for AI-writing tells (hedging
   filler, false balance, generic openers). It doesn't rewrite anything —
   it produces a checklist. Keeping this separate means the model isn't
   grading its own homework in the same breath it wrote it.

3. **One draft, three shapes.** A story usually needs to exist as a full
   article, a two-paragraph newsletter blurb, and a social post — and
   these aren't the same text at different lengths, they're different
   jobs. `formatters/` takes one approved draft and produces
   format-specific output (WordPress REST payload, newsletter markdown,
   social copy) rather than asking a model to "also make it shorter."

## Architecture

```
sources (RSS/URLs)
      │
      ▼
  ingest.py ──────► storage.py (SQLite: dedupe, run history)
      │
      ▼
  scoring.py ───────► editorial brief (config.yaml) decides the bar
      │  (stories above threshold only)
      ▼
  drafting.py ──────► angle + outline + draft, in your style guide's voice
      │
      ▼
  qa.py ────────────► claims-to-verify checklist + style flags (advisory only)
      │
      ▼
  formatters/ ──────► wordpress.py | newsletter.py | social.py
      │
      ▼
  outbox/ (human reviews and approves before anything goes live)
```

Nothing auto-publishes. The pipeline's job is to get a story from "raw
source" to "ready for an editor's final pass" — the publish action itself
stays a deliberate, human step.

## What it replaces

Manually, this loop was: skim ~15–20 sources a day, keep a mental (or
spreadsheet) tally of what's worth chasing, draft from scratch, and
manually reformat the same piece three times for three channels. Signal
collapses the first-pass triage and the reformatting, which is where most
of the wasted editorial hours actually go — not in the writing itself.

## Setup

```bash
git clone <this-repo>
cd content-workflow
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
```

## Usage

Run the full pipeline against configured sources:

```bash
python cli.py run --config config.yaml
```

Try it with no API key and no live sources, using the bundled example:

```bash
python cli.py demo
```

This runs the same code path against `examples/sample_run/` fixtures and
writes formatted output to `outbox/`, so you can see the full shape of
the pipeline — ingest → score → draft → QA → format — without any
credentials.

Other flags:

```bash
python cli.py run --config config.yaml --min-score 7   # raise the bar
python cli.py run --config config.yaml --format newsletter,social
python cli.py status                                    # what's in the pipeline right now
```

## Editorial brief

`config.yaml` holds the actual editorial judgment as configuration, not
buried in a prompt string:

```yaml
brief:
  audience: "short-term rental hosts and revenue managers"
  voice: "direct, specific, allergic to fluff — trade-press, not marketing copy"
  what_matters: "operational or pricing implications for hosts, not vendor announcements"
  what_to_skip: "funding rounds, generic listicles, anything without a number in it"
scoring:
  threshold: 7        # 1-10, stories below this don't get drafted
  weights:
    relevance: 0.4
    timeliness: 0.3
    specificity: 0.3
```

Changing the brief changes what the pipeline chases — no code edits
needed to point this at a different beat or publication.

## Project layout

```
content-workflow/
├── cli.py                  # entry point
├── config.yaml             # editorial brief, sources, thresholds
├── src/
│   ├── pipeline.py         # orchestrator
│   ├── ingest.py           # RSS/URL fetch + clean extraction
│   ├── scoring.py          # newsworthiness scoring against the brief
│   ├── drafting.py         # angle, outline, draft generation
│   ├── qa.py                # claim extraction + style flags (advisory)
│   ├── storage.py          # SQLite state: dedupe, run history
│   ├── llm.py               # thin Anthropic API wrapper, swappable
│   └── formatters/
│       ├── wordpress.py    # REST API-ready payload
│       ├── newsletter.py   # markdown blurb
│       └── social.py       # short-form copy
├── examples/sample_run/    # fixtures for `cli.py demo`
└── tests/
```

## Tests

```bash
pytest tests/ -v
```

Scoring and drafting tests run against a mocked LLM client so they're
fast, deterministic, and don't burn API credits in CI.

## Extending it

- **New source type:** add a fetcher to `ingest.py` following the
  existing `Source` protocol — RSS and raw-URL are implemented, a
  Slack-channel or Google-Alert source would slot in the same way.
- **New output channel:** add a module to `formatters/` that takes an
  approved `Draft` and returns channel-specific output. Nothing else
  needs to change.
- **Swap the model:** `llm.py` is a single thin wrapper — point it at a
  different provider without touching scoring/drafting logic.

## License

MIT
