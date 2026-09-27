#!/usr/bin/env python3
"""Single CLI entrypoint for the wiki-trends skill.

Every command prints one JSON object to stdout and nothing else (so a small
model can call it, read the JSON, and move on without parsing prose or huge
daily-data dumps). Errors are also JSON: {"error": "..."}.

Commands:
  resolve  --topic T --langs pl,cs,uk [--source-lang en]
  compare  --topic T --langs pl,cs,uk --start 2023-09-01 --end 2025-09-01
           [--granularity daily|monthly] [--source-lang en] [--question "..."]
  refine   --run-id ID [--add-lang X] [--start ...] [--end ...] [--question ...]
  show     --run-id ID
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts import analyze, charts, pageviews, report, wikidata
else:
    from . import analyze, charts, pageviews, report, wikidata

RUNS_DIR = Path(__file__).resolve().parent.parent / "output" / "runs"
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "output" / "artifacts"


def _run_id(topic: str, langs: list[str], start: str, end: str, granularity: str, source_lang: str) -> str:
    payload = json.dumps(
        {"topic": topic, "langs": sorted(langs), "start": start, "end": end,
         "granularity": granularity, "source_lang": source_lang},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _project_for_lang(lang: str) -> str:
    return f"{lang}.wikipedia"


def _run_pipeline(topic: str, langs: list[str], start: str, end: str,
                   granularity: str, source_lang: str, question: str | None) -> dict:
    rid = _run_id(topic, langs, start, end, granularity, source_lang)

    resolution = wikidata.resolve_titles(topic, langs, source_lang=source_lang)

    series_points: dict[str, list[tuple[str, int]]] = {}
    stats_list: list[analyze.SeriesStats] = []

    for lang, title in resolution.resolved.items():
        project = _project_for_lang(lang)
        try:
            article_series = pageviews.fetch_article_series(
                project, title, start, end, granularity=granularity
            )
        except pageviews.PageviewsError as e:
            resolution.unresolved.append(lang)
            continue

        try:
            agg_series = pageviews.fetch_project_aggregate(
                project, start, end, granularity="monthly"
            )
            agg_points = agg_series.points
        except pageviews.PageviewsError:
            agg_points = None

        series_points[lang] = article_series.points
        stats_list.append(
            analyze.analyze_series(
                lang=lang, project=project, article=title,
                points=article_series.points, start=start, end=end,
                granularity=granularity, project_aggregate_points=agg_points,
            )
        )

    chart_path = ARTIFACTS_DIR / rid / "chart.png"
    charts.plot_comparison(
        series_points,
        title=f"{topic}: Wikipedia interest by language",
        out_path=chart_path,
    )

    ranked = analyze.rank_by_growth(stats_list)
    next_steps = _suggest_next_steps(ranked, resolution.unresolved)

    report_path = ARTIFACTS_DIR / rid / "report.pdf"
    report.build_report(
        out_path=report_path,
        topic=topic,
        start=start,
        end=end,
        chart_path=chart_path,
        stats=ranked,
        unresolved_langs=resolution.unresolved,
        user_question=question,
        next_steps=next_steps,
    )

    run_record = {
        "run_id": rid,
        "topic": topic,
        "source_lang": source_lang,
        "langs": langs,
        "start": start,
        "end": end,
        "granularity": granularity,
        "question": question,
        "resolved_titles": resolution.resolved,
        "unresolved_langs": resolution.unresolved,
        "series_points": series_points,
        "stats": [dataclasses.asdict(s) for s in ranked],
        "chart_path": str(chart_path),
        "report_path": str(report_path),
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with (RUNS_DIR / f"{rid}.json").open("w", encoding="utf-8") as f:
        json.dump(run_record, f, ensure_ascii=False)

    return _summary(run_record)


def _suggest_next_steps(ranked: list[analyze.SeriesStats], unresolved: list[str]) -> list[str]:
    steps = []
    low_conf = [s.lang for s in ranked if s.confidence in ("low", "none")]
    if low_conf:
        steps.append(
            f"Re-check {', '.join(low_conf)} over a longer window or a related "
            f"cluster of articles before trusting their trend."
        )
    if unresolved:
        steps.append(
            f"Manually confirm whether {', '.join(unresolved)} Wikipedia truly "
            f"has no coverage of this topic, or the article just isn't linked "
            f"on Wikidata."
        )
    top = ranked[0] if ranked else None
    if top and top.confidence in ("high", "medium") and top.growth_pct is not None:
        if top.growth_pct > 0:
            steps.append(
                f"{top.lang} shows the strongest reliable growth "
                f"({top.growth_pct:+.1f}%) — validate with a smaller pilot "
                f"before committing localization budget."
            )
        else:
            steps.append(
                f"No language in this comparison shows reliable growth "
                f"(best is {top.lang} at {top.growth_pct:+.1f}%) — before "
                f"investing here, try a broader topic cluster or a longer "
                f"time window."
            )
    steps.append(
        "Widen the topic to a cluster of related articles (via Wikidata "
        "'related items') to reduce single-article noise."
    )
    return steps


def _summary(run_record: dict) -> dict:
    return {
        "run_id": run_record["run_id"],
        "topic": run_record["topic"],
        "period": f"{run_record['start']} to {run_record['end']}",
        "ranked_languages": [
            {
                "lang": s["lang"],
                "growth_pct": s["growth_pct"],
                "confidence": s["confidence"],
                "why": s["confidence_reasons"][0] if s["confidence_reasons"] else None,
                "normalized_share_end_pct": s["normalized_share_end_pct"],
            }
            for s in run_record["stats"]
        ],
        "unresolved_langs": run_record["unresolved_langs"],
        "chart_path": run_record["chart_path"],
        "report_path": run_record["report_path"],
    }


def cmd_resolve(args: argparse.Namespace) -> dict:
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    res = wikidata.resolve_titles(args.topic, langs, source_lang=args.source_lang)
    return {
        "topic": res.topic,
        "wikidata_id": res.wikidata_id,
        "resolved": res.resolved,
        "unresolved": res.unresolved,
    }


def cmd_compare(args: argparse.Namespace) -> dict:
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    return _run_pipeline(
        topic=args.topic, langs=langs, start=args.start, end=args.end,
        granularity=args.granularity, source_lang=args.source_lang,
        question=args.question,
    )


def cmd_refine(args: argparse.Namespace) -> dict:
    run_path = RUNS_DIR / f"{args.run_id}.json"
    if not run_path.exists():
        return {"error": f"Unknown run_id: {args.run_id}"}
    with run_path.open("r", encoding="utf-8") as f:
        prev = json.load(f)

    langs = list(prev["langs"])
    if args.add_lang:
        for l in args.add_lang.split(","):
            l = l.strip()
            if l and l not in langs:
                langs.append(l)

    return _run_pipeline(
        topic=prev["topic"],
        langs=langs,
        start=args.start or prev["start"],
        end=args.end or prev["end"],
        granularity=args.granularity or prev["granularity"],
        source_lang=prev["source_lang"],
        question=args.question or prev["question"],
    )


def cmd_show(args: argparse.Namespace) -> dict:
    run_path = RUNS_DIR / f"{args.run_id}.json"
    if not run_path.exists():
        return {"error": f"Unknown run_id: {args.run_id}"}
    with run_path.open("r", encoding="utf-8") as f:
        return _summary(json.load(f))


def main() -> None:
    parser = argparse.ArgumentParser(prog="wiki-trends")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("resolve")
    p.add_argument("--topic", required=True)
    p.add_argument("--langs", required=True)
    p.add_argument("--source-lang", default="en")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("compare")
    p.add_argument("--topic", required=True)
    p.add_argument("--langs", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--granularity", default="daily", choices=["daily", "monthly"])
    p.add_argument("--source-lang", default="en")
    p.add_argument("--question", default=None)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("refine")
    p.add_argument("--run-id", required=True)
    p.add_argument("--add-lang", default=None)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--granularity", default=None, choices=["daily", "monthly", None])
    p.add_argument("--question", default=None)
    p.set_defaults(func=cmd_refine)

    p = sub.add_parser("show")
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=cmd_show)

    args = parser.parse_args()
    try:
        result = args.func(args)
    except Exception as e:  # noqa: BLE001 - CLI boundary, must always emit JSON
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
