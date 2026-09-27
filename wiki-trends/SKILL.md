---
name: wiki-trends
description: Analyzes Wikipedia pageview trends across languages and topics via the Wikimedia Pageviews API, to help B2C product teams decide which topics or languages to invest in. Generates a comparison chart and a one-page shareable PDF report with growth rates, a data-quality/confidence rating per language, and explicit assumptions and limitations. Use when the user wants to compare interest in a topic across Wikipedia language editions, check whether interest in a topic is growing, or decide which language/market to prioritize based on Wikipedia traffic.
license: MIT
compatibility: Requires Python 3.10+, a virtualenv with requirements.txt installed, and outbound HTTPS access to wikimedia.org and wikidata.org.
metadata:
  author: pavlo-nikolaiev
  version: "1.0"
---

# Wikipedia trend analysis for B2C product decisions

This skill answers questions like:

- "Compare growth of interest in intermittent fasting between Polish and Czech Wikipedia over the last two years."
- "Is interest in astronomy growing on Ukrainian Wikipedia, and how much should I trust that growth?"
- "Compare interest in learning English across these language editions and suggest which audiences to look into next."

It does **not** guess these answers itself. It always calls `scripts/cli.py`,
which does the real work (fetching data, computing growth/confidence,
drawing the chart, writing the PDF) and returns a small JSON summary. Read
that JSON and explain it in your own words — do not re-derive growth numbers
by eyeballing a chart.

## Setup (once per environment)

```bash
cd wiki-trends
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

All commands below assume you're in `wiki-trends/` with the venv active.
Every command below is: `python3 -m scripts.cli <command> ...`

## Workflow

### 1. New comparison → `compare`

```bash
python3 -m scripts.cli compare \
  --topic "Intermittent fasting" \
  --langs pl,cs \
  --start 2023-09-01 --end 2025-09-01 \
  --question "Порівняй зростання інтересу до інтервального голодування в польськомовній та чеськомовній Wikipedia за останні два роки."
```

- `--topic`: an article title as it appears on the *source* Wikipedia
  (default source language is English; override with `--source-lang`).
  The skill resolves this to the matching article title in each requested
  language via Wikidata — you do not need to know how the topic is spelled
  in Polish or Czech.
- `--langs`: comma-separated Wikipedia language codes (`pl`, `cs`, `uk`,
  `de`, `en`, ...).
- `--start` / `--end`: `YYYY-MM-DD`. Data only exists from 2015-07-01
  onward.
- `--question`: optional, pass the user's original question verbatim (any
  language, including Ukrainian) — it's printed on the PDF for traceability.

This prints one JSON object: a `run_id`, a `ranked_languages` list (growth
%, confidence label, one-line reason, normalized traffic share), which
languages had no matching article (`unresolved_langs`), and paths to the
generated `chart_path` (PNG) and `report_path` (PDF, one page).

**Read `ranked_languages` and `why` directly — do not open the PDF or PNG
to extract numbers.** Only reference the file paths when telling the user
where to find the shareable artifacts.

### 2. User refines the question → `refine`

If the user asks a follow-up ("also check German", "extend to three years",
"what about a different date range") **reuse the same `run_id`** instead of
starting over — this reuses cached API responses and is much cheaper/faster
than calling `compare` again from scratch:

```bash
python3 -m scripts.cli refine --run-id <run_id> --add-lang de
python3 -m scripts.cli refine --run-id <run_id> --start 2022-01-01 --end 2025-09-01
```

`refine` re-runs the full pipeline for the (possibly extended) language set
and date range and overwrites that run's chart/report in place. It returns
the same JSON shape as `compare`.

### 3. Recall a previous result → `show`

If you already have a `run_id` from earlier in the conversation and just
need the summary again (e.g. after the transcript scrolled past it), use
`show` instead of re-running the pipeline:

```bash
python3 -m scripts.cli show --run-id <run_id>
```

### 4. Just resolving titles (rarely needed standalone)

`compare` and `refine` already do this internally. Use `resolve` directly
only if the user explicitly wants to know what an article is called in
another language, without fetching any traffic data:

```bash
python3 -m scripts.cli resolve --topic "Intermittent fasting" --langs pl,cs,uk
```

## Interpreting results for the user

- **Never state a growth number without its confidence label and the
  reason behind it.** `low`/`none` confidence means the trend is likely
  noise (too little traffic, one viral day, missing data, or a weak trend
  fit) — say so plainly instead of presenting it as a clean finding.
- **Growth % is not the same as popularity.** Use `normalized_share_end_pct`
  (traffic share of the article vs. its whole Wikipedia edition) to compare
  how big the audience actually is, since raw view counts aren't comparable
  across editions of very different sizes.
- If `unresolved_langs` is non-empty, tell the user explicitly which
  languages were excluded and why (no matching Wikidata sitelink for that
  edition) — don't silently drop them from your summary.
- Every report already includes a written "Assumptions & limitations"
  section and "Suggested next steps" — when you summarize the report for
  the user, carry those caveats over; don't strip them out for brevity.
- A Wikipedia pageview is a *curiosity* signal, not purchase intent. Phrase
  recommendations as "worth investigating further," not "will sell."

## Troubleshooting

- `{"error": "No data for this request (404)..."}` for one language during
  `compare`/`refine`: that language gets moved into `unresolved_langs`
  automatically; the rest of the comparison still completes. No action
  needed unless *all* requested languages fail this way, which usually
  means the topic itself doesn't exist as a Wikidata item — try a more
  standard/canonical title.
- SSL certificate errors on some systems: the client already pins
  `certifi`'s CA bundle (see `scripts/pageviews.py` / `scripts/wikidata.py`);
  if this still fails, the environment's `pip install -r requirements.txt`
  probably didn't complete — re-run setup.

## Extending this skill

See `references/DATA_NOTES.md` for the reasoning behind the data choices
(bot filtering, normalization, confidence scoring) and `ROADMAP.md` for how
to grow this into a heavier research tool (topic clusters, larger date
ranges, anomaly correlation, etc.) as usage grows beyond quick one-page
reports.
