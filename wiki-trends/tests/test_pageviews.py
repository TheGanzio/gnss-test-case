import urllib.error

import pytest

from scripts import pageviews


def _fake_response(n=5, start_ts="2025010100"):
    items = []
    ts = int(start_ts[:8])
    for i in range(n):
        # crude but fine for a test: just bump the day digit
        day_ts = f"{start_ts[:6]}{(int(start_ts[6:8]) + i):02d}00"
        items.append({
            "project": "en.wikipedia",
            "article": "Test",
            "granularity": "daily",
            "timestamp": day_ts,
            "access": "all-access",
            "agent": "user",
            "views": 100 + i,
        })
    return {"items": items}


def test_fetch_article_series_parses_points(monkeypatch):
    monkeypatch.setattr(pageviews, "_http_get_json", lambda url: _fake_response(n=3))
    series = pageviews.fetch_article_series("en.wikipedia", "Test", "2025-01-01", "2025-01-03")
    assert series.points == [
        ("2025-01-01", 100),
        ("2025-01-02", 101),
        ("2025-01-03", 102),
    ]


def test_fetch_article_series_uses_cache_on_second_call(monkeypatch):
    calls = {"n": 0}

    def fake_get(url):
        calls["n"] += 1
        return _fake_response(n=2)

    monkeypatch.setattr(pageviews, "_http_get_json", fake_get)
    pageviews.fetch_article_series("en.wikipedia", "Test", "2025-01-01", "2025-01-02")
    pageviews.fetch_article_series("en.wikipedia", "Test", "2025-01-01", "2025-01-02")
    assert calls["n"] == 1


def test_404_raises_pageviews_error(monkeypatch):
    def raise_404(req, timeout=20, context=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(pageviews.urllib.request, "urlopen", raise_404)
    with pytest.raises(pageviews.PageviewsError):
        pageviews.fetch_article_series("en.wikipedia", "Nonexistent Article", "2025-01-01", "2025-01-02")
