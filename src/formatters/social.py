"""Formats an approved draft as short-form social copy."""
from __future__ import annotations

from ..drafting import Draft


def format_social(draft: Draft) -> str:
    hook = draft.pull_quote or draft.dek
    lines = [
        hook.strip(),
        "",
        draft.headline,
        "",
        draft.score.item.url,
    ]
    return "\n".join(lines)


def write_social(draft: Draft, path: str) -> str:
    content = format_social(draft)
    with open(path, "w") as f:
        f.write(content)
    return path
