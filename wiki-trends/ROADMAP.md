# Roadmap: from a quick one-pager to a heavier research tool

The current pipeline answers a single comparison in a few CLI calls and one
PDF. This is deliberately the smallest thing that's genuinely useful. As
usage grows toward "complex research scenarios" and "larger data volumes"
(per the task brief), the natural next steps, roughly in priority order:

## 1. Topic clusters instead of single articles

Right now one topic = one Wikidata item = one article per language. Real
questions ("interest in astronomy") span many articles (Astronomy,
Astrophysics, individual planets, telescopes, ...). Next step: pull
Wikidata's "related items" / instance-of / subclass-of relations (or a
curated category) to build a small article cluster per topic, sum/aggregate
their series, and report cluster coverage (how many of the cluster's
articles exist per language) as part of the confidence signal.

## 2. Storage: JSON files → SQLite/DuckDB

The current cache is one-JSON-file-per-request, fine for interactive,
single-user use. Once queries start covering many languages × many articles
× multi-year daily data, move to SQLite (or DuckDB for faster columnar
aggregation) so:
- repeated `refine` calls query a shared local table instead of
  reassembling many JSON files,
- growth/aggregation math can be pushed into SQL instead of Python loops,
- multiple concurrent runs don't fight over the same cache files.

## 3. Concurrent/batched fetching

`fetch_article_series` and `fetch_project_aggregate` are called sequentially
per language. For a 10+ language comparison this is the main latency cost.
Add a small async batch fetcher (asyncio + aiohttp, or a thread pool) with
per-host rate limiting and exponential backoff — Wikimedia's API is public
and shared, so this needs to stay polite, not just fast.

## 4. Statistical rigor beyond linear trend + z-score spikes

Current spike/trend detection is intentionally simple (z-score > 3,
least-squares slope). For bigger studies: STL/seasonal decomposition (many
topics have weekly/seasonal patterns that a flat linear fit misreads as
noise), a real changepoint detection method for "when did this trend
start," and bootstrap confidence intervals on the growth % instead of a
single point estimate.

## 5. Explaining spikes, not just flagging them

Today a spike just lowers confidence. A useful next step: cross-reference
spike dates against Wikipedia's own "In the news" / current events feed (or
a news API) so the report can say *why* a day looks anomalous instead of
just "this day is an outlier."

## 6. Multi-page / interactive deep-dive mode

Keep the one-page PDF as the default shareable artifact, but add an
optional `--depth deep` mode that produces a longer HTML report (interactive
charts, per-article breakdown, full data table) for users who want to dig in
after the one-pager gets them interested. This should be a separate code
path, not a bigger default report — the one-page constraint is a feature,
not a limitation to work around.

## 7. Evaluation harness

Add a small fixed set of known topics with expected qualitative outcomes
(e.g. "a topic with a single Wikipedia-wide news spike should be scored
medium/low, not high") and run the pipeline against them as a regression
test whenever the analysis logic changes — this is different from the unit
tests in `tests/`, which check code correctness, not analytical judgment.

## 8. Caching Wikidata resolution alongside pageviews

Title resolution is already cached, but a dedicated `references/title_map`
built up over time (topic → resolved titles per language) would let the
skill skip the Wikidata round-trip entirely for topics it has already
resolved in a previous session, not just within one cache lifetime.
