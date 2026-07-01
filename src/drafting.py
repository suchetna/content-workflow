"""
Drafting: turn a scored story into an angle, outline, and full draft.

Split into two model calls (angle+outline, then full draft) rather than
one, because an outline is cheap to reject and re-run — you don't want to
regenerate 650 words because the structural decision was wrong.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .llm import LLMClient
from .scoring import Score

ANGLE_SYSTEM = """You are a trade-press editor developing a story angle. \
Voice: {voice}

Given the one true thing that matters about this story, propose the angle \
that makes it worth a reader's time — not a summary of the news, but the \
specific implication or tension that earns the piece.

(Task: propose an angle.)"""

ANGLE_USER = """The one thing that matters: {one_thing_that_matters}

Original story context:
{title}
{text}

Return JSON with keys: angle (one sentence — the story's actual argument, \
not its topic), outline (a list of 3-5 section beats, each one sentence)."""

DRAFT_SYSTEM = """You are a trade-press writer. Voice: {voice}

Write the full piece from this angle and outline. Target roughly \
{target_word_count} words. Open with the specific implication, not \
scene-setting. Every claim should be traceable to the source material — \
do not invent statistics, quotes, or dates not present in the source.

(Task: write the full draft.)"""

DRAFT_USER = """Angle: {angle}

Outline:
{outline}

Source material:
{text}

Return JSON with keys: headline, dek (one-sentence subhead), body \
(the full piece, plain text with \\n\\n paragraph breaks){pull_quote_key}."""


@dataclass
class Draft:
    score: Score
    angle: str
    outline: list[str]
    headline: str
    dek: str
    body: str
    pull_quote: str = ""


def propose_angle(score: Score, brief: dict, llm: LLMClient) -> tuple[str, list[str]]:
    system = ANGLE_SYSTEM.format(voice=brief["voice"])
    user = ANGLE_USER.format(
        one_thing_that_matters=score.one_thing_that_matters,
        title=score.item.title,
        text=score.item.text[:4000],
    )
    result = llm.complete_json(system, user)
    return result["angle"], result["outline"]


def write_draft(
    score: Score,
    angle: str,
    outline: list[str],
    brief: dict,
    drafting_config: dict,
    llm: LLMClient,
) -> Draft:
    system = DRAFT_SYSTEM.format(
        voice=brief["voice"],
        target_word_count=drafting_config.get("target_word_count", 600),
    )
    pull_quote_key = (
        ", pull_quote (one striking sentence lifted from the body)"
        if drafting_config.get("include_pull_quote")
        else ""
    )
    user = DRAFT_USER.format(
        angle=angle,
        outline="\n".join(f"- {beat}" for beat in outline),
        text=score.item.text[:4000],
        pull_quote_key=pull_quote_key,
    )
    result = llm.complete_json(system, user)
    return Draft(
        score=score,
        angle=angle,
        outline=outline,
        headline=result["headline"],
        dek=result["dek"],
        body=result["body"],
        pull_quote=result.get("pull_quote", ""),
    )


def draft_story(score: Score, brief: dict, drafting_config: dict, llm: LLMClient) -> Draft:
    angle, outline = propose_angle(score, brief, llm)
    return write_draft(score, angle, outline, brief, drafting_config, llm)
