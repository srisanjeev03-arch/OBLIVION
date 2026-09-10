"""Provider-agnostic access to a model, with availability as a first-class fact.

The system must work with no model at all. That is not a degraded mode to be
apologised for - deterministic policy, safety validation and evidence are the
authoritative path, and the model only ever explains and suggests. So every
provider here answers ``available()`` honestly, and a provider that cannot serve
says so rather than raising from somewhere deep in a request.

The local-model target is the Qwen family on a modest GPU (the stated
development target is 8 GB of VRAM), which is why :class:`LocalQwenProvider`
checks for its runtime and weights before claiming availability and never
imports its dependencies at module import time. Nothing else in the codebase
mentions Qwen: swapping in another model means adding a provider, not editing
the advisor.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Final

from oblivion.ai.schema import ModelIdentity

logger = logging.getLogger(__name__)

ENV_PROVIDER: Final = "OBLIVION_AI_PROVIDER"
ENV_MODEL_ID: Final = "OBLIVION_AI_MODEL"
ENV_MODEL_PATH: Final = "OBLIVION_AI_MODEL_PATH"
ENV_ENDPOINT: Final = "OBLIVION_AI_ENDPOINT"

#: How long a single completion may take. A model that stalls must not stall an
#: operation: the advisory is optional, the erasure pipeline is not.
DEFAULT_TIMEOUT_SECONDS: Final = 30.0


class ProviderError(Exception):
    """Raised when a provider that claimed availability then failed."""


class AIProvider(ABC):
    """Somewhere a prompt can be sent. Returns raw text; validates nothing.

    Deliberately narrow. A provider's only job is transport - all judgement
    about whether an answer is acceptable happens in
    :mod:`oblivion.ai.validation`, so a new provider cannot accidentally widen
    what the system will believe.
    """

    @property
    @abstractmethod
    def identity(self) -> ModelIdentity:
        """Which model this is, recorded on every advisory it produces."""

    @abstractmethod
    def available(self) -> bool:
        """Whether a request would actually reach a model right now."""

    @abstractmethod
    def complete(self, prompt: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
        """Return raw model output. May raise :class:`ProviderError`."""

    @property
    def unavailable_reason(self) -> str:
        """Why this provider cannot serve, for the caller to record."""
        return "No reason given."


class NullProvider(AIProvider):
    """The provider a deployment gets when it has configured no model.

    Not a stub or a placeholder: it is the correct provider for a system with no
    AI configured, and it makes that state explicit everywhere rather than
    leaving ``None`` to be checked at each call site.
    """

    def __init__(self, reason: str = "No AI provider is configured.") -> None:
        self._reason = reason

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity(model_id="none", model_version="0", provider="null")

    def available(self) -> bool:
        return False

    @property
    def unavailable_reason(self) -> str:
        return self._reason

    # The unused parameters below are the AIProvider interface. Keeping the
    # signature identical across providers is what lets the advisor treat them
    # interchangeably, which is the whole point of the abstraction.
    def complete(
        self,
        prompt: str,  # noqa: ARG002 - provider interface
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,  # noqa: ARG002 - provider interface
    ) -> str:
        raise ProviderError(
            "NullProvider serves no completions. Callers must check available() "
            "and continue without an advisory."
        )


class StaticProvider(AIProvider):
    """Returns a fixed response. For tests and for the evaluation harness.

    Real, not simulated: it exercises the whole validation path with a known
    input, which is exactly what a reproducible evaluation needs. It is never
    selected by :func:`provider_from_env`, so it cannot become a production
    fallback that quietly answers for a missing model.
    """

    def __init__(
        self,
        response: str,
        *,
        model_id: str = "static",
        model_version: str = "1",
        fail: bool = False,
    ) -> None:
        self._response = response
        self._identity = ModelIdentity(
            model_id=model_id, model_version=model_version, provider="static"
        )
        self._fail = fail

    @property
    def identity(self) -> ModelIdentity:
        return self._identity

    def available(self) -> bool:
        return not self._fail

    @property
    def unavailable_reason(self) -> str:
        return "StaticProvider was configured to be unavailable."

    def complete(
        self,
        prompt: str,  # noqa: ARG002 - provider interface
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,  # noqa: ARG002 - provider interface
    ) -> str:
        if self._fail:
            raise ProviderError("StaticProvider was configured to fail")
        return self._response


class LocalQwenProvider(AIProvider):
    """A local Qwen-family model, when one is actually present.

    Availability is checked, never assumed: the runtime must be importable and
    the weights must exist on disk. Both are verified without importing the
    runtime at module load, so this file is safe to import on a machine that has
    no ML stack at all - which is every machine currently running this suite.

    The development target is 8 GB of VRAM, so a quantized local build is the
    expected deployment. This class does not enforce that; it reports what it
    found and lets the operator choose.
    """

    def __init__(
        self,
        model_path: str | None = None,
        model_id: str = "qwen",
        model_version: str = "unknown",
    ) -> None:
        self._model_path = model_path or os.environ.get(ENV_MODEL_PATH, "")
        self._identity = ModelIdentity(
            model_id=model_id, model_version=model_version, provider="local-qwen"
        )
        self._reason = ""

    @property
    def identity(self) -> ModelIdentity:
        return self._identity

    def available(self) -> bool:
        if not self._model_path:
            self._reason = (
                f"{ENV_MODEL_PATH} is not set, so no local model weights were named."
            )
            return False
        if not os.path.exists(self._model_path):
            self._reason = (
                "No model weights were found at the configured path. The advisory "
                "layer stays unavailable rather than falling back to another model."
            )
            return False
        try:
            import importlib.util

            if importlib.util.find_spec("llama_cpp") is None:
                self._reason = (
                    "No local inference runtime is installed (llama_cpp not found)."
                )
                return False
        except Exception as exc:  # noqa: BLE001 - availability check must not raise
            self._reason = f"Runtime probe failed: {type(exc).__name__}"
            return False
        return True

    @property
    def unavailable_reason(self) -> str:
        return self._reason or "Local model availability has not been checked."

    def complete(
        self,
        prompt: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,  # noqa: ARG002 - provider interface
    ) -> str:
        if not self.available():
            raise ProviderError(self.unavailable_reason)
        # Imported here, not at module scope: this file must import cleanly on a
        # machine with no ML stack, and it does.
        from llama_cpp import Llama

        model = Llama(model_path=self._model_path, verbose=False)
        completion = model(prompt, max_tokens=512, temperature=0.0)
        try:
            text = completion["choices"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Local model returned an unexpected response shape: {exc}"
            ) from None
        return str(text)


def provider_from_env(env: dict[str, str] | None = None) -> AIProvider:
    """Select a provider from configuration.

    Unset, unknown, or misconfigured all resolve to :class:`NullProvider` with a
    reason attached. Falling back to a different model than the one requested
    would be worse than having none: an advisory would then be attributed to a
    model that did not produce it.
    """
    source = env if env is not None else dict(os.environ)
    name = (source.get(ENV_PROVIDER) or "").strip().lower()

    if not name or name == "none":
        return NullProvider("No AI provider is configured; advisories are disabled.")

    if name in ("qwen", "local-qwen", "local"):
        return LocalQwenProvider(
            model_path=source.get(ENV_MODEL_PATH),
            model_id=source.get(ENV_MODEL_ID, "qwen"),
        )

    return NullProvider(
        f"Unknown AI provider {name!r}. Advisories stay disabled rather than "
        "silently using a different model."
    )
