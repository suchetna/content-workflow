"""
Thin wrapper around the Anthropic API.

Kept deliberately small and isolated: every other module talks to
`LLMClient`, never to the SDK directly. Swapping providers or adding
retries/caching/logging happens in exactly one place.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

DEFAULT_MODEL = os.environ.get("SIGNAL_MODEL", "claude-sonnet-4-6")


@dataclass
class LLMResponse:
    text: str
    raw: Any = None


class LLMClient:
    """Wraps the Anthropic Messages API. Swap this class to change providers."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None  # lazy import/init so `cli.py demo` needs no key

    def _ensure_client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set. Add it to .env, or run "
                    "`python cli.py demo` to try the pipeline without live calls."
                )
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> LLMResponse:
        client = self._ensure_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return LLMResponse(text=text, raw=resp)

    def complete_json(self, system: str, prompt: str, max_tokens: int = 1500) -> dict:
        """Ask for structured JSON output and parse it, tolerating code fences."""
        system_json = (
            system
            + "\n\nRespond with ONLY a valid JSON object. No preamble, no markdown "
            "fences, no commentary before or after."
        )
        resp = self.complete(system_json, prompt, max_tokens=max_tokens)
        cleaned = resp.text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())


class FakeLLMClient(LLMClient):
    """
    Deterministic stand-in used by `cli.py demo` and tests.

    Returns canned, structurally-valid responses keyed off simple heuristics
    in the prompt, so the full pipeline shape is exercised without any
    network call or API key.
    """

    def __init__(self):
        super().__init__(model="fake-demo-model")

    def complete(self, system: str, prompt: str, max_tokens: int = 1500) -> LLMResponse:
        raise NotImplementedError("FakeLLMClient only supports complete_json")

    def complete_json(self, system: str, prompt: str, max_tokens: int = 1500) -> dict:
        if "score this story" in system.lower():
            if "series a" in prompt.lower() or "reimagining hospitality" in prompt.lower():
                return {
                    "relevance": 2,
                    "timeliness": 3,
                    "specificity": 2,
                    "score": 2.3,
                    "one_thing_that_matters": (
                        "A vendor raised funding; no product or operational "
                        "detail disclosed."
                    ),
                    "reasoning": (
                        "Funding announcement with no concrete implication for "
                        "hosts — matches the brief's 'what to skip' list."
                    ),
                }
            return {
                "relevance": 8,
                "timeliness": 7,
                "specificity": 9,
                "score": 8.0,
                "one_thing_that_matters": (
                    "The platform's new minimum-stay override changes how hosts "
                    "should set weekend pricing rules, effective next month."
                ),
                "reasoning": (
                    "Concrete operational change with a clear before/after for "
                    "hosts, not a vendor announcement."
                ),
            }
        if "propose an angle" in system.lower():
            return {
                "angle": (
                    "What the new minimum-stay override actually means for your "
                    "weekend pricing rules"
                ),
                "outline": [
                    "The change: what's different starting next month",
                    "Why the platform made this call (and what they're not saying)",
                    "The three pricing-rule adjustments hosts should make now",
                    "What to watch for in the first billing cycle",
                ],
            }
        if "write the full draft" in system.lower():
            return {
                "headline": (
                    "The new minimum-stay override quietly rewrites your "
                    "weekend pricing playbook"
                ),
                "dek": (
                    "A policy change effective next month changes how weekend "
                    "minimum stays interact with dynamic pricing rules — here's "
                    "what to adjust before the next billing cycle."
                ),
                "body": (
                    "Starting next month, the platform will let guests override "
                    "host-set weekend minimum stays under specific conditions. "
                    "For hosts running aggressive weekend rate rules, this is "
                    "not a footnote — it changes the assumption those rules "
                    "were built on.\n\n"
                    "Three adjustments worth making before the change lands: "
                    "first, audit any rule that assumes a guaranteed two-night "
                    "weekend minimum. Second, model what a one-night override "
                    "does to your realized ADR across a typical month. Third, "
                    "set a manual review trigger for the first billing cycle "
                    "rather than trusting the automation blind.\n\n"
                    "The platform has not said how often the override will "
                    "actually trigger in practice — that's the number worth "
                    "watching once real data comes in."
                ),
                "pull_quote": (
                    "This is not a footnote — it changes the assumption those "
                    "rules were built on."
                ),
            }
        if "extract every factual claim" in system.lower():
            return {
                "claims": [
                    {
                        "claim": "The override takes effect 'next month'",
                        "needs_verification": True,
                        "reason": "Exact date not confirmed in source material",
                    },
                    {
                        "claim": "The override applies only 'under specific conditions'",
                        "needs_verification": True,
                        "reason": "Conditions not enumerated — needs the platform's exact policy text",
                    },
                ],
                "ai_writing_tells": [],
                "style_notes": [],
            }
        raise NotImplementedError(f"FakeLLMClient has no canned response for this prompt")
