"""
QA: produce a human-review checklist for a draft. This module never edits
the draft — it only flags. Keeping generation and verification as separate
passes means the model isn't grading its own work in the same breath it
wrote it, and it keeps a clear human checkpoint before anything publishes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .drafting import Draft
from .llm import LLMClient

QA_SYSTEM = """You are a fact-checking editor reviewing a draft before \
publication. You do not rewrite anything — you produce a checklist.

(Task: extract every factual claim in this draft that a fact-checker \
would need to verify before publish, and separately flag any AI-writing \
tells: hedging filler, false balance where none is warranted, generic \
openers, or claims presented with more certainty than the source \
material supports.)"""

QA_USER = """Draft:
{headline}
{dek}

{body}

Source material the draft was based on:
{source_text}

Return JSON with keys:
- claims: list of objects with "claim", "needs_verification" (bool), "reason"
- ai_writing_tells: list of strings, each a specific phrase or pattern to reconsider
- style_notes: list of strings, other editorial notes (voice/register mismatches, etc.)"""


@dataclass
class QAReport:
    draft: Draft
    claims: list[dict] = field(default_factory=list)
    ai_writing_tells: list[str] = field(default_factory=list)
    style_notes: list[str] = field(default_factory=list)

    @property
    def needs_human_review(self) -> bool:
        return any(c.get("needs_verification") for c in self.claims) or bool(
            self.ai_writing_tells
        )

    def as_checklist(self) -> str:
        lines = [f"QA checklist — {self.draft.headline}", ""]
        if self.claims:
            lines.append("Claims to verify before publish:")
            for c in self.claims:
                flag = "⚠" if c.get("needs_verification") else "✓"
                lines.append(f"  {flag} {c['claim']} — {c.get('reason', '')}")
        if self.ai_writing_tells:
            lines.append("")
            lines.append("Writing tells to reconsider:")
            for tell in self.ai_writing_tells:
                lines.append(f"  - {tell}")
        if self.style_notes:
            lines.append("")
            lines.append("Style notes:")
            for note in self.style_notes:
                lines.append(f"  - {note}")
        if not any([self.claims, self.ai_writing_tells, self.style_notes]):
            lines.append("No flags raised. Still get a second pair of eyes.")
        return "\n".join(lines)


def run_qa(draft: Draft, llm: LLMClient) -> QAReport:
    system = QA_SYSTEM
    user = QA_USER.format(
        headline=draft.headline,
        dek=draft.dek,
        body=draft.body,
        source_text=draft.score.item.text[:4000],
    )
    result = llm.complete_json(system, user)
    return QAReport(
        draft=draft,
        claims=result.get("claims", []),
        ai_writing_tells=result.get("ai_writing_tells", []),
        style_notes=result.get("style_notes", []),
    )
