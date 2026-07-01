from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from src.ingest import load_fixtures
from src.llm import LLMClient, FakeLLMClient
from src.pipeline import run_pipeline
from src.storage import Store

load_dotenv()


def _load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@click.group()
def cli():
    """Signal — an editorial content pipeline."""


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config.yaml")
@click.option("--min-score", type=float, default=None, help="Override scoring threshold")
@click.option("--format", "formats", default=None, help="Comma-separated: wordpress,newsletter,social")
def run(config, min_score, formats):
    """Run the full pipeline against live configured sources."""
    cfg = _load_config(config)
    llm = LLMClient()
    formats_list = formats.split(",") if formats else None

    result = run_pipeline(cfg, llm, min_score_override=min_score, formats_override=formats_list)
    _report(result)


@cli.command()
def demo():
    """Run the pipeline against bundled fixtures with a mocked LLM — no API key needed."""
    cfg = _load_config("config.yaml")
    cfg["storage"]["db_path"] = "signal_demo.db"
    Path(cfg["storage"]["db_path"]).unlink(missing_ok=True)

    fixtures_dir = Path("examples/sample_run")
    fixture_dicts = [
        json.loads(p.read_text()) for p in sorted(fixtures_dir.glob("*.json"))
    ]
    raw_items = load_fixtures(fixture_dicts)

    llm = FakeLLMClient()
    click.echo("Running Signal in demo mode (fake LLM, no API key required)...\n")
    result = run_pipeline(cfg, llm, raw_items=raw_items)
    _report(result)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config.yaml")
def status(config):
    """Show recent pipeline activity."""
    cfg = _load_config(config)
    store = Store(cfg["storage"]["db_path"])
    counts = store.counts_by_status()
    click.echo("Status counts:")
    for status_name, count in counts.items():
        click.echo(f"  {status_name}: {count}")
    click.echo("\nRecent items:")
    for row in store.recent(10):
        click.echo(f"  [{row['status']:>10}] {row.get('score', '—')}  {row['title']}")


def _report(result):
    click.echo(f"Scored: {len(result.scored)} items")
    click.echo(f"Skipped (below threshold): {result.skipped}")
    click.echo(f"Drafted: {len(result.drafted)}")
    for draft, report in result.drafted:
        flag = "⚠ needs review" if report.needs_human_review else "✓ clean"
        click.echo(f"  - {draft.headline}  [{flag}]")
    if result.outbox_paths:
        click.echo(f"\nWrote {len(result.outbox_paths)} files to outbox/:")
        for p in result.outbox_paths:
            click.echo(f"  {p}")


if __name__ == "__main__":
    cli()
