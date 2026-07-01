"""
Pipeline: wires ingest -> dedupe -> score -> draft -> qa -> format together.
Each stage's output is what the next stage needs, nothing more — this is
what makes it possible to swap or extend any one stage independently.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import ingest as ingest_mod
from . import scoring as scoring_mod
from . import drafting as drafting_mod
from . import qa as qa_mod
from .formatters import wordpress, newsletter, social
from .llm import LLMClient
from .storage import Store


@dataclass
class PipelineResult:
    scored: list[scoring_mod.Score]
    drafted: list[tuple[drafting_mod.Draft, qa_mod.QAReport]]
    skipped: int
    outbox_paths: list[str]


def run_pipeline(
    config: dict,
    llm: LLMClient,
    raw_items: list[ingest_mod.RawItem] | None = None,
    min_score_override: float | None = None,
    formats_override: list[str] | None = None,
) -> PipelineResult:
    store = Store(config["storage"]["db_path"])
    brief = config["brief"]
    threshold = min_score_override or config["scoring"]["threshold"]
    weights = config["scoring"]["weights"]
    formats = formats_override or config["output"]["formats"]
    outbox_dir = Path(config["output"]["outbox_dir"])
    outbox_dir.mkdir(parents=True, exist_ok=True)

    items = raw_items if raw_items is not None else ingest_mod.ingest_all(
        config["sources"]
    )

    new_items = []
    for item in items:
        if store.already_seen(item.fingerprint):
            continue
        store.upsert(
            item.fingerprint,
            title=item.title,
            source_name=item.source_name,
            url=item.url,
            status="ingested",
        )
        new_items.append(item)

    scored = scoring_mod.score_all(new_items, brief, weights, llm)

    drafted: list[tuple[drafting_mod.Draft, qa_mod.QAReport]] = []
    outbox_paths: list[str] = []
    skipped = 0

    for score in scored:
        fp = score.item.fingerprint
        if not score.clears(threshold):
            store.upsert(fp, status="skipped", score=score.score)
            skipped += 1
            continue

        draft = drafting_mod.draft_story(score, brief, config["drafting"], llm)
        report = qa_mod.run_qa(draft, llm)
        drafted.append((draft, report))

        paths = _write_outputs(draft, report, formats, outbox_dir, llm)
        outbox_paths.extend(paths)

        store.upsert(
            fp,
            status="qa_done",
            score=score.score,
            headline=draft.headline,
            outbox_paths=paths,
        )

    return PipelineResult(
        scored=scored, drafted=drafted, skipped=skipped, outbox_paths=outbox_paths
    )


def _write_outputs(
    draft: drafting_mod.Draft,
    report: qa_mod.QAReport,
    formats: list[str],
    outbox_dir: Path,
    llm: LLMClient,
) -> list[str]:
    slug = "".join(c if c.isalnum() else "-" for c in draft.headline.lower())[:60].strip("-")
    paths = []

    if "wordpress" in formats:
        p = outbox_dir / f"{slug}.wordpress.json"
        wordpress.write_wordpress_payload(draft, str(p))
        paths.append(str(p))

    if "newsletter" in formats:
        p = outbox_dir / f"{slug}.newsletter.md"
        newsletter.write_newsletter(draft, str(p), llm=None)  # keep deterministic in demo
        paths.append(str(p))

    if "social" in formats:
        p = outbox_dir / f"{slug}.social.txt"
        social.write_social(draft, str(p))
        paths.append(str(p))

    qa_path = outbox_dir / f"{slug}.qa-checklist.txt"
    with open(qa_path, "w") as f:
        f.write(report.as_checklist())
    paths.append(str(qa_path))

    return paths
