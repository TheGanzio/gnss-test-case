# How this was tested

Two layers of verification, both required by the task brief: automated
correctness tests, and a live run on the target cheap/small model class.

## 1. Automated tests (offline, no network, no LLM)

```bash
cd wiki-trends
source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest tests/ -q
```

13 tests, covering:

- `test_analyze.py` — growth/confidence math: steady growth scores
  high-confidence, a flat series shows ~0% growth, a single-day spike is
  detected and demoted to lower confidence, empty/incomplete data is
  flagged rather than silently producing a number, and normalization
  against a project's aggregate traffic is computed correctly.
- `test_pageviews.py` — Wikimedia API response parsing (mocked HTTP),
  on-disk caching (a second identical call makes zero HTTP requests), and
  that a 404 (e.g. wrong article title) raises a clear error instead of
  crashing.
- `test_wikidata.py` — title resolution via Wikidata sitelinks (mocked
  HTTP): exact-title match, fallback to `wbsearchentities` when the exact
  title isn't found, and the case where a topic doesn't resolve for any
  language.
- `test_report_smoke.py` — full chart + one-page PDF generation with
  Cyrillic input text, asserting the PDF is exactly one page. This test is
  what caught two real bugs during development (see below).

I verified these aren't hollow tests by deliberately breaking things while
building the pipeline and confirming the suite failed appropriately: fpdf2's
`multi_cell` leaves the text cursor at the block's right edge instead of the
left margin by default, which silently corrupted the layout of every
paragraph after the first one — `test_report_smoke.py` (and manual PDF
inspection, see below) caught this. I also found by manual inspection (not
a test) that the normalized traffic-share numbers were rounding to
`0.000%` in the PDF table because real article shares are single-digit
parts-per-million — fixed by switching that column's display units to ppm.

## 2. Live run on the target model (claude-haiku-4-5)

The brief requires checking the full scenario on a fast/cheap model like
Claude Haiku 4.5, since the skill must stay usable there even though users
may pick stronger models. `tests/live/run_live_test.py` is a small,
skill-external harness (not part of `requirements.txt` — it needs the
`anthropic` SDK, which the skill itself never imports) that:

1. Loads `SKILL.md` into the system prompt, exactly as an agent runtime
   would after activating this skill.
2. Gives the model exactly one tool, `bash`, scoped to this directory.
3. Sends one of the task brief's own example questions, in Ukrainian.
4. Lets the model drive the CLI itself (no hardcoded commands) and answer
   in its own words.
5. Saves the full transcript for inspection.

Run it yourself (needs `ANTHROPIC_API_KEY` with available credit, or point
`LIVE_TEST_MODEL` at an OpenRouter-compatible cheap/free model if adapting
the client):

```bash
cd wiki-trends
source .venv/bin/activate
pip install anthropic
ANTHROPIC_API_KEY=sk-ant-... python3 tests/live/run_live_test.py "<question>"
```

### What I checked in the transcripts (not just "it ran")

Saved transcripts: `tests/live/transcript_1_astronomy_uk.md`,
`tests/live/transcript_2_fasting_pl_cs.md`,
`tests/live/transcript_3_stalker2_uk_de.md`.

For each run I cross-checked the model's final Ukrainian answer against the
raw JSON the CLI actually returned, specifically:

- **Numbers aren't invented.** The growth %, confidence label, and
  normalized share the model quotes match the JSON verbatim (e.g. run 1:
  JSON says `growth_pct: -92.6`, `confidence: "high"`; the model's answer
  says "-92.6%" and correctly flags this as a *decrease*, not growth —
  important because the user's question was phrased assuming growth).
- **The caveat behind the confidence label is actually used, not just the
  label.** Run 1's JSON confidence is `"high"` overall, but its `why` field
  says volatility is elevated (CV=1.16). The model's answer explicitly
  downgrades its own certainty because of that reason text, rather than
  reporting "high confidence" at face value — this is the exact behavior
  `SKILL.md` asks for ("never state a growth number without its confidence
  label *and the reason behind it*").
- **Unresolved languages are surfaced, not dropped.** Run 2 asked to
  compare Polish and Czech; Polish had no matching Wikidata sitelink for
  "Intermittent fasting" and landed in `unresolved_langs`. The model told
  the user Polish was excluded and why, instead of silently answering only
  for Czech.
- **The model used the CLI correctly on the first try** in both runs —
  correct flags, correct date format, correct topic string — with no
  retries needed, on `claude-haiku-4-5-20251001`, which is the point of the
  "must work on a fast/cheap model" requirement.
- **Cost/efficiency**: run 1 used 5719 input / 620 output tokens, run 2
  used 5687 input / 506 output tokens, run 3 used 5802 input / 619 output
  tokens, in a single tool-call round trip each. Input tokens are dominated
  by `SKILL.md` itself (loaded once per conversation by a real agent
  runtime, not per turn), not by data dumped from the CLI — the CLI
  intentionally returns a compact summary JSON instead of raw daily
  pageview series for exactly this reason.
- **Run 3 (ad hoc, not from the task brief's examples)** asked about
  "Stalker 2" — a colloquial name, not a Wikipedia article title. The model
  resolved it to the correct canonical title
  (`S.T.A.L.K.E.R. 2: Heart of Chornobyl`) itself, without being told the
  exact title, and correctly used the normalized ppm share (not just the
  growth %) to point out that Ukrainian Wikipedia's audience share for the
  topic is far larger than German's despite German having the bigger raw
  growth percentage — showing the model engaged with *why* the normalized
  metric exists, not just repeating numbers.

## Known limitation of this test

Both live runs happened to only need one CLI call each (`compare`) to fully
answer the question. I did not get a live-model transcript exercising
`refine` (follow-up question reusing a `run_id`) end-to-end — that path is
covered by the automated tests and by manual runs during development (see
shell history / the `refine --add-lang uk,de` example in `SKILL.md`), but
not by a live small-model transcript. If extending this test suite, that's
the next scenario to add.
