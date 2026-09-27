"""Client for the Wikimedia Pageviews (Analytics Query Service) REST API.

Docs: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from . import cache

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

USER_AGENT = "wiki-trends-skill/1.0 (Genesis AI Product Engineering School case)"
BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews"

# Pageviews data has a short lag and Wikimedia only guarantees data from
# 2015-07-01 onward for the per-article endpoint.
EARLIEST_DATE = "2015-07-01"


class PageviewsError(RuntimeError):
    pass


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise PageviewsError(
                f"No data for this request (404). URL: {url}. "
                "This usually means the article title is wrong for this "
                "project, or there is no traffic in the requested range."
            ) from e
        raise PageviewsError(f"HTTP {e.code} fetching {url}") from e


def _fmt_date(d: str) -> str:
    """Accepts 'YYYY-MM-DD' or 'YYYYMMDD', returns 'YYYYMMDD'."""
    return d.replace("-", "")


@dataclass
class Series:
    project: str
    article: str | None  # None for project-level aggregate series
    granularity: str
    points: list[tuple[str, int]]  # (YYYY-MM-DD, views)


def fetch_article_series(
    project: str,
    article: str,
    start: str,
    end: str,
    granularity: str = "daily",
    access: str = "all-access",
    agent: str = "user",
) -> Series:
    """Fetch daily/monthly pageviews for one article in one project.

    `agent="user"` (the default) excludes bot/spider traffic, which is
    important: raw "all-agents" counts are frequently dominated by crawlers
    and would make trend comparisons meaningless.
    """
    article_enc = urllib.parse.quote(article.replace(" ", "_"), safe="")
    params = {
        "project": project,
        "article": article,
        "start": _fmt_date(start),
        "end": _fmt_date(end),
        "granularity": granularity,
        "access": access,
        "agent": agent,
    }
    cached = cache.get("pageviews_article", params)
    if cached is not None:
        data = cached
    else:
        url = (
            f"{BASE}/per-article/{project}/{access}/{agent}/"
            f"{article_enc}/{granularity}/{_fmt_date(start)}/{_fmt_date(end)}"
        )
        data = _http_get_json(url)
        cache.set("pageviews_article", params, data)

    points = [
        (_timestamp_to_date(item["timestamp"]), item["views"])
        for item in data.get("items", [])
    ]
    return Series(project=project, article=article, granularity=granularity, points=points)


def fetch_project_aggregate(
    project: str,
    start: str,
    end: str,
    granularity: str = "monthly",
    access: str = "all-access",
    agent: str = "user",
) -> Series:
    """Fetch total pageviews for an entire project (used to normalize an
    article's views against the size of its language edition)."""
    params = {
        "project": project,
        "start": _fmt_date(start),
        "end": _fmt_date(end),
        "granularity": granularity,
        "access": access,
        "agent": agent,
    }
    cached = cache.get("pageviews_aggregate", params)
    if cached is not None:
        data = cached
    else:
        url = (
            f"{BASE}/aggregate/{project}/{access}/{agent}/"
            f"{granularity}/{_fmt_date(start)}/{_fmt_date(end)}"
        )
        data = _http_get_json(url)
        cache.set("pageviews_aggregate", params, data)

    points = [
        (_timestamp_to_date(item["timestamp"]), item["views"])
        for item in data.get("items", [])
    ]
    return Series(project=project, article=None, granularity=granularity, points=points)


def _timestamp_to_date(ts: str) -> str:
    # API timestamps look like "2025010100" (YYYYMMDDHH)
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
