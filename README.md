# Genesis AI Product Engineering School — Case Submission

**Case:** build an [Agent Skill](https://agentskills.io/specification) that
lets an AI agent analyze Wikipedia pageview trends across languages/topics,
so B2C founders can decide which topics or markets to invest in.

**Submission:** [`wiki-trends/`](wiki-trends/) — the skill itself.

## Quick start

```bash
cd wiki-trends
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 -m scripts.cli compare \
  --topic "Intermittent fasting" --langs pl,cs \
  --start 2023-09-01 --end 2025-09-01
```

This resolves the article title in each language via Wikidata, fetches
pageviews from the Wikimedia Analytics API, computes a growth rate and a
data-quality confidence rating per language, and writes a comparison chart
(PNG) and a one-page shareable report (PDF) to `wiki-trends/output/`.

## Where to look

- [`wiki-trends/SKILL.md`](wiki-trends/SKILL.md) — the skill's instructions
  for an agent: CLI usage, how to interpret results, troubleshooting.
- [`wiki-trends/references/DATA_NOTES.md`](wiki-trends/references/DATA_NOTES.md)
  — why the analysis is built the way it is (bot filtering, normalization
  across editions of different sizes, confidence scoring, title resolution).
- [`wiki-trends/ROADMAP.md`](wiki-trends/ROADMAP.md) — how this grows into a
  heavier research tool (topic clusters, bigger storage, async fetching,
  deeper stats) as usage scales up.
- [`wiki-trends/TESTING.md`](wiki-trends/TESTING.md) — how this was
  verified: the automated test suite, and a live run on
  `claude-haiku-4-5` (the fast/cheap model the brief requires checking
  against) with saved transcripts in `wiki-trends/tests/live/`.
- [`wiki-trends/scripts/`](wiki-trends/scripts/) — the actual implementation
  (Python): Wikidata title resolution, the Wikimedia Pageviews client,
  trend/confidence analysis, chart generation, PDF report generation, and
  the `cli.py` entrypoint an agent calls.

## Note on AI tool usage

Per the task brief, AI-assisted development is expected here ("Використовуй
AI-інструменти під час розробки та будь готовий пояснити, як ти перевіряв
їхній результат"). Claude Code was used throughout development. Every
piece of generated code was run against real data and/or automated tests
before being kept — see `TESTING.md` for specifics, including two bugs
(an fpdf2 cursor-positioning bug that corrupted PDF layout, and a
percentage-formatting bug that rounded small traffic shares to 0.000%)
that were caught by actually running the pipeline against live Wikimedia
data and inspecting the rendered PDF output, not just by reading the code.
