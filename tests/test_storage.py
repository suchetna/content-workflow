import os
import tempfile

from src.storage import Store


def test_dedupe_and_upsert():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        store = Store(db_path)
        fp = "abc123"
        assert store.already_seen(fp) is False
        store.upsert(fp, title="T", source_name="s", url="https://x.com", status="ingested")
        assert store.already_seen(fp) is True

        store.upsert(fp, status="qa_done", score=8.5, headline="H", outbox_paths=["a.json"])
        recent = store.recent(5)
        assert recent[0]["status"] == "qa_done"
        assert recent[0]["score"] == 8.5
