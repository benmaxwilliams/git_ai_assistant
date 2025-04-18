from __future__ import annotations

import abc
import os
import time
from typing import List, Type

from packaging import version

# ------------------------------------------------------------------ config ---
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0"))
SYSTEM_PROMPT = (
    "You are an expert Git assistant. Return ONLY Windows‑compatible "
    "Git commands that could be saved verbatim to a .bat file. "
    "No comments or explanations."
)
FALLBACK_ORDER = (
    os.getenv("GIT_ASSISTANT_PROVIDERS", "openai,dummy").split(",")
)

# -------------------------------------------------------- framework / errors ---
class ProviderError(RuntimeError):
    """Signals any provider‑specific failure suitable for fallback handling."""


class LLMProvider(abc.ABC):
    NAME: str = "base"

    @abc.abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the model’s reply or raise ProviderError."""


# ----------------------------------------------------------- built‑in providers
class OpenAIProvider(LLMProvider):
    """
    Default provider using the *openai‑python* SDK (legacy or ≥ 1.0 autodetected).
    """

    NAME = "openai"

    def __init__(self, base_url: str | None = None, retries: int = 2, debug: bool = False):
        import openai  # local import keeps dependency optional

        self.openai = openai
        self.retries = retries
        self.debug = debug
        self.client = self._build_client(base_url)

    # ------------------------------------------------------------------- helpers
    def _build_client(self, base_url: str | None):
        if version.parse(self.openai.__version__) >= version.parse("1.0.0"):
            from openai import OpenAI  # type: ignore
            return OpenAI(base_url=base_url) if base_url else OpenAI()
        # legacy 0.28.x
        if base_url:
            self.openai.api_base = base_url  # type: ignore[attr-defined]
        return self.openai

    # ------------------------------------------------------------ main interface
    def complete(self, prompt: str) -> str:  # noqa: D401
        attempt, wait = 0, 2.0
        while True:
            try:
                if hasattr(self.client, "chat"):  # new style
                    resp = self.client.chat.completions.create(
                        model=DEFAULT_MODEL,
                        temperature=DEFAULT_TEMP,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    )
                    return resp.choices[0].message.content.strip()

                # legacy style
                resp = self.client.ChatCompletion.create(
                    model=DEFAULT_MODEL,
                    temperature=DEFAULT_TEMP,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                return resp.choices[0].message.content.strip()

            except self.openai.error.RateLimitError as e:
                if "exceeded" in str(e).lower():
                    raise ProviderError("OpenAI quota exhausted") from e
                if attempt >= self.retries:
                    raise ProviderError("OpenAI rate‑limited, retries exceeded") from e
                if self.debug:
                    print(f"[openai] 429 → retry in {wait:.0f}s (attempt {attempt+1})")
                time.sleep(wait)
                attempt += 1
                wait *= 2

            except self.openai.error.AuthenticationError as e:
                raise ProviderError("OpenAI authentication failed") from e
            except self.openai.OpenAIError as e:
                raise ProviderError(f"OpenAI API error: {e}") from e


class DummyEchoProvider(LLMProvider):
    """Always returns a harmless echo block – keeps the tool usable offline."""

    NAME = "dummy"

    def complete(self, prompt: str) -> str:  # noqa: D401
        return f"REM Echo provider – no LLM available\nREM Prompt was: {prompt}"


# ------------------------------------------------------------ provider factory
class ProviderFactory:
    _registry: dict[str, Type[LLMProvider]] = {}

    # ------ registry  ----------------------------------------------------------
    @classmethod
    def register(cls, provider_cls: Type[LLMProvider]):
        cls._registry[provider_cls.NAME] = provider_cls

    # ------ selection ----------------------------------------------------------
    @classmethod
    def first_available(cls, order: List[str], **kwargs) -> LLMProvider:
        errors: dict[str, str] = {}
        for name in order:
            prov_cls = cls._registry.get(name)
            if not prov_cls:
                errors[name] = "not registered"
                continue
            try:
                return prov_cls(**kwargs)  # type: ignore[arg-type]
            except ProviderError as e:
                errors[name] = str(e)
        raise RuntimeError(
            "No LLM provider succeeded: "
            + ", ".join(f"{k}→{v}" for k, v in errors.items())
        )


# register built‑ins
ProviderFactory.register(OpenAIProvider)
ProviderFactory.register(DummyEchoProvider)
