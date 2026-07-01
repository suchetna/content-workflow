from src.ingest import RawItem, load_fixtures


def test_fingerprint_is_stable_and_url_based():
    a = RawItem(
        source_name="s", title="Title", url="https://x.com/1", published="", text="a"
    )
    b = RawItem(
        source_name="s", title="Title", url="https://x.com/1", published="", text="different text"
    )
    assert a.fingerprint == b.fingerprint  # dedupe key ignores body text


def test_fingerprint_differs_for_different_urls():
    a = RawItem(source_name="s", title="T", url="https://x.com/1", published="", text="a")
    b = RawItem(source_name="s", title="T", url="https://x.com/2", published="", text="a")
    assert a.fingerprint != b.fingerprint


def test_load_fixtures():
    items = load_fixtures(
        [{"source_name": "s", "title": "T", "url": "https://x.com", "published": "", "text": "body"}]
    )
    assert len(items) == 1
    assert items[0].title == "T"
