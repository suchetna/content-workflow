"""Formats an approved draft as a short newsletter blurb (not the full piece)."""
from __future__ import annotations

from ..drafting import Draft
from ..llm import LLMClient

BLURB_SYSTEM = """You write newsletter blurbs. Voice: {voice}

Condense this full piece into a 2-3 sentence newsletter blurb that makes \
a reader want to click through — don't just truncate the article, write \
the blurb as its own object with its own hook.

(Task: write the full draft.)"""

BLURB_USER = """Headline: {headline}
Full piece: {body}

Return JSON with keys: headline (can differ slightly from the article's), \
dek, body (the 2-3 sentence blurb, no pull_quote key needed)."""


def format_newsletter(draft: Draft, llm: LLMClient | None = None) -> str:
    if llm is not None:
        try:
            result = llm.complete_json(
                BLURB_SYSTEM.format(voice="direct, specific, trade-press"),
                BLURB_USER.format(headline=draft.headline, body=draft.body),
            )
            blurb = result["body"]
            headline = result.get("headline", draft.headline)
        except Exception:
            blurb = draft.dek
            headline = draft.headline
    else:
        blurb = draft.dek
        headline = draft.headline

    return (
        f"### {headline}\n\n"
        f"{blurb}\n\n"
        f"[Read the full story]({draft.score.item.url})\n"
    )


def write_newsletter(draft: Draft, path: str, llm: LLMClient | None = None) -> str:
    content = format_newsletter(draft, llm)
    with open(path, "w") as f:
        f.write(content)
    return path
