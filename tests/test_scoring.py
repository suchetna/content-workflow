from src.ingest import RawItem
from src.llm import FakeLLMClient
from src.scoring import score_item

BRIEF = {
    "audience": "short-term rental hosts",
    "what_matters": "operational implications",
    "what_to_skip": "funding announcements",
}
WEIGHTS = {"relevance": 0.4, "timeliness": 0.3, "specificity": 0.3}


def test_high_signal_story_clears_threshold():
    item = RawItem(
        source_name="s",
        title="Platform changes weekend minimum-stay rules",
        url="https://x.com/1",
        published="",
        text="The platform announced changes to minimum-stay overrides for hosts.",
    )
    score = score_item(item, BRIEF, WEIGHTS, FakeLLMClient())
    assert score.clears(7)
    assert score.score >= 7


def test_low_signal_story_does_not_clear_threshold():
    item = RawItem(
        source_name="s",
        title="Vendor X raises Series A to reimagining hospitality",
        url="https://x.com/2",
        published="",
        text="Vendor X raised a Series A round.",
    )
    score = score_item(item, BRIEF, WEIGHTS, FakeLLMClient())
    assert not score.clears(7)
