"""
Scoring: decide whether a raw item clears the bar to be drafted, and why.

This is a separate step from drafting on purpose. A model asked to "write
about X" will write about X regardless of whether X is a real story —
so Signal asks a narrower, prior question first: is this worth a human's
attention, and what's the one thing that actually matters about it?
"""
from __future__ import annotations

from dataclasses import dataclass

from .ingest import RawItem
from .llm import LLMClient

SYSTEM_PROMPT = """You are an experienced trade-press editor. Score this \
story for whether it's worth drafting into a piece for the following brief.

Audience: {audience}
What matters to this audience: {what_matters}
What to skip: {what_to_skip}

Score honestly. Most raw items are not worth drafting — press releases, \
generic trend pieces, and anything without a concrete implication for the \
audience should score low. Reserve high scores for stories with a real, \
specific operational or informational stake for the reader."""

USER_PROMPT = """Title: {title}
Source: {source_name}
URL: {url}

Content:
{text}

Score this story on three dimensions from 1-10:
- relevance: how directly this affects the target audience
- timeliness: how time-sensitive this is
- specificity: how concrete vs. generic this is (numbers, names, dates > vague trends)

Return JSON with keys: relevance, timeliness, specificity, score \
(weighted average), one_thing_that_matters (one sentence — the actual \
news, stripped of framing), reasoning (one sentence on why this score)."""


@dataclass
class Score:
    item: RawItem
    relevance: float
    timeliness: float
    specificity: float
    score: float
    one_thing_that_matters: str
    reasoning: str

    def clears(self, threshold: float) -> bool:
        return self.score >= threshold


def score_item(item: RawItem, brief: dict, weights: dict, llm: LLMClient) -> Score:
    system = SYSTEM_PROMPT.format(
        audience=brief["audience"],
        what_matters=brief["what_matters"],
        what_to_skip=brief["what_to_skip"],
    )
    # Note: "score this story" must appear for FakeLLMClient's routing in demo mode.
    system += "\n\n(Task: score this story.)"
    user = USER_PROMPT.format(
        title=item.title,
        source_name=item.source_name,
        url=item.url,
        text=item.text[:4000],
    )
    result = llm.complete_json(system, user)

    weighted = (
        result["relevance"] * weights.get("relevance", 1 / 3)
        + result["timeliness"] * weights.get("timeliness", 1 / 3)
        + result["specificity"] * weights.get("specificity", 1 / 3)
    )
    return Score(
        item=item,
        relevance=result["relevance"],
        timeliness=result["timeliness"],
        specificity=result["specificity"],
        score=round(result.get("score", weighted), 2),
        one_thing_that_matters=result["one_thing_that_matters"],
        reasoning=result["reasoning"],
    )


def score_all(items: list[RawItem], brief: dict, weights: dict, llm: LLMClient) -> list[Score]:
    return [score_item(item, brief, weights, llm) for item in items]
