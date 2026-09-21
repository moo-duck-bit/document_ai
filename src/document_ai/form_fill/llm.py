"""LLM interface for free-text fields — stub default, swappable provider.

Contract (team / DocAgent):
- Structured fields (amounts, dates, Req IDs, frequency, …) stay rules/facts only.
- Only free_text (narrative) may optionally call an LLM with few-shot hints.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class FreeTextLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> str: ...


class StubFreeTextLLM(FreeTextLLM):
    """Deterministic fallback — uses hints and templates, no external API."""

    def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        hints = context.get("free_text_hints") or {}
        if "overview" in prompt.lower() and hints.get("system_overview"):
            return str(hints["system_overview"])
        if "architecture" in prompt.lower() and hints.get("architecture_narrative"):
            return str(hints["architecture_narrative"])
        if hints.get("system_overview"):
            return str(hints["system_overview"])
        return context.get("fallback_text", "")


class OptionalEnvFreeTextLLM(FreeTextLLM):
    """Optional provider: uses OpenAI-compatible chat when env is set; else stub.

    Env:
      DOCUMENT_AI_FREE_TEXT_LLM=1 (or true/yes) to enable
      DOCUMENT_AI_FREE_TEXT_LLM_MODEL (default gpt-4o-mini)
      OPENAI_API_KEY (required when enabled)
    """

    def __init__(self) -> None:
        self._stub = StubFreeTextLLM()
        self.enabled = str(os.getenv("DOCUMENT_AI_FREE_TEXT_LLM") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.model = os.getenv("DOCUMENT_AI_FREE_TEXT_LLM_MODEL") or "gpt-4o-mini"
        self.api_key = os.getenv("OPENAI_API_KEY") or ""

    def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        # Never invent structured facts — if caller marks structured, force stub/empty.
        if context.get("field_kind") in {"structured", "rule", "fact"}:
            return self._stub.generate(prompt, context=context)
        if not self.enabled or not self.api_key:
            return self._stub.generate(prompt, context=context)
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=self.api_key)
            hints = context.get("free_text_hints") or {}
            few_shot = context.get("few_shot_examples") or []
            system = (
                "You draft free-text narrative cells only. "
                "Do not invent amounts, dates, Req IDs, or frequencies; "
                "those come from rules/facts."
            )
            user_parts = [prompt]
            if hints:
                user_parts.append(f"Hints: {hints}")
            if few_shot:
                user_parts.append(f"Few-shot: {few_shot[:3]}")
            if context.get("fallback_text"):
                user_parts.append(f"Fallback if unsure: {context['fallback_text']}")
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": "\n".join(user_parts)},
                ],
                temperature=0.2,
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or self._stub.generate(prompt, context=context)
        except Exception:
            return self._stub.generate(prompt, context=context)


def get_free_text_llm() -> FreeTextLLM:
    """Factory used by FormFillEngine — optional LLM for free_text only."""
    return OptionalEnvFreeTextLLM()
