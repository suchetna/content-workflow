"""
Formats an approved draft as a WordPress REST API-ready payload
(POST /wp-json/wp/v2/posts). Left as draft status — publishing is a
deliberate human action, not something this pipeline does automatically.
"""
from __future__ import annotations

import json

from ..drafting import Draft


def format_wordpress(draft: Draft) -> dict:
    paragraphs = draft.body.split("\n\n")
    blocks = []
    if draft.pull_quote:
        # Insert the pull quote after the first paragraph, Gutenberg-block style.
        blocks.append(f"<!-- wp:paragraph --><p>{paragraphs[0]}</p><!-- /wp:paragraph -->")
        blocks.append(
            f"<!-- wp:quote --><blockquote class=\"wp-block-quote\"><p>{draft.pull_quote}</p></blockquote><!-- /wp:quote -->"
        )
        rest = paragraphs[1:]
    else:
        rest = paragraphs
    for p in rest:
        blocks.append(f"<!-- wp:paragraph --><p>{p}</p><!-- /wp:paragraph -->")

    return {
        "title": draft.headline,
        "excerpt": draft.dek,
        "status": "draft",  # never auto-publish
        "content": "\n".join(blocks),
        "meta": {
            "signal_source_url": draft.score.item.url,
            "signal_editorial_score": draft.score.score,
            "signal_angle": draft.angle,
        },
    }


def write_wordpress_payload(draft: Draft, path: str) -> str:
    payload = format_wordpress(draft)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path
