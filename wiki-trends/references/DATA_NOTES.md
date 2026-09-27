# Data notes: why the pipeline is built this way

Background reading for anyone (human or agent) who needs to understand *why*
a number in a report looks the way it does, or wants to extend the analysis.

## Bot traffic

The Wikimedia Pageviews API can report `agent=all-agents`, `agent=user`, or
`agent=spider`. `all-agents` traffic is frequently dominated by crawlers and
monitoring bots — using it would make "interest" comparisons meaningless.
This skill always requests `agent=user`. This is a deliberate simplification
(not exposed as a CLI flag) so the interface stays small for a cheap model
to drive correctly.

## Why growth is a start-window vs. end-window comparison, not last-day vs.
first-day

A single day's view count is noisy (a small news mention can 10x it
overnight). `analyze.py` averages the first ~15% and last ~15% of the
requested date range and compares those two averages. A linear trend
(least-squares slope + R²) is computed separately and reported alongside,
so the agent/user can see whether the growth is a consistent trend
(high R²) or mostly driven by the endpoints (low R²).

## Why normalization matters

English Wikipedia gets roughly 100x more traffic than, say, Ukrainian
Wikipedia. Comparing raw view counts across editions would always favor
large editions regardless of actual relative interest. Each article's views
are also compared against `aggregate` (whole-project) traffic for the same
period, producing a "share of edition traffic" number (expressed in the PDF
as parts-per-million, since the shares are typically in the 1–100 ppm
range and round to 0.00% otherwise). This estimates *relative* interest
within each language's own reading population.

This normalization is still imperfect: it doesn't account for a language
edition's overall topic mix (e.g. a health/wellness-heavy edition vs. a
politics-heavy one), device/traffic-source differences, or mobile vs.
desktop split. Treat the ppm numbers as directional, not exact.

## Cross-language title resolution (Wikidata)

Wikipedia editions don't share article titles. `wikidata.py` looks up the
Wikidata item behind the source-language title (exact match first, then
`wbsearchentities` as a fallback for fuzzy titles) and reads its
`sitelinks` to find the matching title in each target language. If a
language has no sitelink, the topic is treated as **not covered** in that
edition (`unresolved`) rather than guessed — a missing article is itself a
signal (that language community hasn't written about this topic yet) worth
surfacing, not something to work around silently.

## Confidence scoring

Each series gets a 0–5 point score based on five independently-checked
issues (total traffic volume, data completeness, day-to-day volatility,
single-day spike dominance, and linear trend fit quality). Score ≥4 → high,
≥2 → medium, else low/none. This is a heuristic, not a statistical test —
it exists to stop the skill from confidently reporting growth numbers that
are actually just noise, spikes, or a data gap. `rank_by_growth` sorts
low-confidence results to the bottom regardless of how large their raw
growth % is, so the report doesn't lead with a number that shouldn't be
trusted.

## Caching

Every raw Wikimedia/Wikidata API response is cached to disk
(`output/cache/`), keyed by a hash of the exact request parameters. This
makes `refine` (add a language, extend a date range) cheap: unchanged parts
of the request are served from cache instead of re-fetched. This also keeps
a cheap/small model's tool loop fast, since repeated or related queries
during one conversation rarely need to hit the network twice for the same
data.
