from src.drafting import draft_story
from src.ingest import RawItem
from src.llm import FakeLLMClient
from src.qa import run_qa
from src.scoring import score_item

BRIEF = {
    "audience": "short-term rental hosts",
    "voice": "direct, trade-press",
    "what_matters": "operational implications",
    "what_to_skip": "funding announcements",
}
WEIGHTS = {"relevance": 0.4, "timeliness": 0.3, "specificity": 0.3}
DRAFTING_CONFIG = {"target_word_count": 600, "include_pull_quote": True}


def _make_score():
    item = RawItem(
        source_name="s",
        title="Platform changes weekend minimum-stay rules",
        url="https://x.com/1",
        published="",
        text="The platform announced changes to minimum-stay overrides for hosts.",
    )
    return score_item(item, BRIEF, WEIGHTS, FakeLLMClient())


def test_draft_story_produces_headline_and_body():
    score = _make_score()
    draft = draft_story(score, BRIEF, DRAFTING_CONFIG, FakeLLMClient())
    assert draft.headline
    assert draft.body
    assert draft.angle
    assert len(draft.outline) >= 3


def test_qa_flags_claims_without_editing_body():
    score = _make_score()
    draft = draft_story(score, BRIEF, DRAFTING_CONFIG, FakeLLMClient())
    original_body = draft.body
    report = run_qa(draft, FakeLLMClient())
    assert draft.body == original_body  # QA must never mutate the draft
    assert report.needs_human_review is True
    assert "QA checklist" in report.as_checklist()
