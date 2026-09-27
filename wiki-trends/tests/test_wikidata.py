from scripts import wikidata


def test_resolve_titles_splits_resolved_and_unresolved(monkeypatch):
    def fake_get(url):
        if "wbgetentities" in url and "sites=enwiki" in url:
            return {"entities": {"Q123": {}}}
        if "wbgetentities" in url and "ids=Q123" in url:
            return {
                "entities": {
                    "Q123": {
                        "sitelinks": {
                            "plwiki": {"title": "Głodówka przerywana"},
                            "cswiki": {"title": "Přerušovaný půst"},
                        }
                    }
                }
            }
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(wikidata, "_http_get_json", fake_get)
    result = wikidata.resolve_titles("Intermittent fasting", ["pl", "cs", "uk"], source_lang="en")

    assert result.resolved == {"pl": "Głodówka przerywana", "cs": "Přerušovaný půst"}
    assert result.unresolved == ["uk"]
    assert result.wikidata_id == "Q123"


def test_resolve_titles_falls_back_to_search_when_exact_title_misses(monkeypatch):
    calls = []

    def fake_get(url):
        calls.append(url)
        if "wbgetentities" in url and "sites=enwiki" in url:
            return {"entities": {"-1": {}}}
        if "wbsearchentities" in url:
            return {"search": [{"id": "Q999"}]}
        if "ids=Q999" in url:
            return {"entities": {"Q999": {"sitelinks": {"ukwiki": {"title": "Тема"}}}}}
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(wikidata, "_http_get_json", fake_get)
    result = wikidata.resolve_titles("Some Fuzzy Title", ["uk"], source_lang="en")

    assert result.wikidata_id == "Q999"
    assert result.resolved == {"uk": "Тема"}
    assert any("wbsearchentities" in c for c in calls)


def test_resolve_titles_all_unresolved_when_topic_not_found(monkeypatch):
    monkeypatch.setattr(
        wikidata, "_http_get_json",
        lambda url: {"entities": {"-1": {}}} if "wbgetentities" in url else {"search": []},
    )
    result = wikidata.resolve_titles("Nonexistent Topic Xyz", ["pl", "cs"], source_lang="en")
    assert result.resolved == {}
    assert result.unresolved == ["pl", "cs"]
