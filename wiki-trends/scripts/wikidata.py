"""Resolve a topic to per-language Wikipedia article titles via Wikidata.

Different language editions of Wikipedia usually don't share exact titles
(e.g. en "Intermittent fasting" vs uk "Інтервальне голодування"). Comparing
pageviews across languages requires finding the matching article in each
edition first. We do this by finding the Wikidata item behind a known title
and reading its sitelinks.
"""

from __future__ import annotations

import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import certifi

from . import cache

USER_AGENT = "wiki-trends-skill/1.0 (Genesis AI Product Engineering School case)"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class WikidataError(RuntimeError):
    pass


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CONTEXT) as resp:
        import json

        return json.loads(resp.read().decode("utf-8"))


@dataclass
class ResolveResult:
    topic: str
    source_lang: str
    resolved: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    wikidata_id: str | None = None


def _find_wikidata_id(title: str, source_lang: str) -> str | None:
    site = f"{source_lang}wiki"
    params = {
        "action": "wbgetentities",
        "sites": site,
        "titles": title,
        "props": "sitelinks",
        "format": "json",
    }
    cached = cache.get("wikidata_lookup", params)
    if cached is not None:
        data = cached
    else:
        url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
        data = _http_get_json(url)
        cache.set("wikidata_lookup", params, data)

    entities = data.get("entities", {})
    if not entities:
        return None
    entity_id = next(iter(entities.keys()))
    if entity_id == "-1":
        return None
    return entity_id


def _search_wikidata_id(title: str, source_lang: str) -> str | None:
    """Fallback when an exact title match fails: use Wikidata's search API."""
    params = {
        "action": "wbsearchentities",
        "search": title,
        "language": source_lang,
        "format": "json",
        "limit": "1",
    }
    cached = cache.get("wikidata_search", params)
    if cached is not None:
        data = cached
    else:
        url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
        data = _http_get_json(url)
        cache.set("wikidata_search", params, data)

    hits = data.get("search", [])
    return hits[0]["id"] if hits else None


def resolve_titles(topic: str, langs: list[str], source_lang: str = "en") -> ResolveResult:
    """Find the article title for `topic` in each of `langs`.

    `topic` should be a title (or close to one) in `source_lang`'s Wikipedia,
    e.g. topic="Intermittent fasting", source_lang="en".
    """
    wikidata_id = _find_wikidata_id(topic, source_lang)
    if wikidata_id is None:
        wikidata_id = _search_wikidata_id(topic, source_lang)
    if wikidata_id is None:
        return ResolveResult(topic=topic, source_lang=source_lang, unresolved=list(langs))

    params = {
        "action": "wbgetentities",
        "ids": wikidata_id,
        "props": "sitelinks",
        "format": "json",
    }
    cached = cache.get("wikidata_entity", params)
    if cached is not None:
        data = cached
    else:
        url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
        data = _http_get_json(url)
        cache.set("wikidata_entity", params, data)

    sitelinks = data.get("entities", {}).get(wikidata_id, {}).get("sitelinks", {})

    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for lang in langs:
        site = f"{lang}wiki"
        if site in sitelinks:
            resolved[lang] = sitelinks[site]["title"]
        else:
            unresolved.append(lang)

    return ResolveResult(
        topic=topic,
        source_lang=source_lang,
        resolved=resolved,
        unresolved=unresolved,
        wikidata_id=wikidata_id,
    )
