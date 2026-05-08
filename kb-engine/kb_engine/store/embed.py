"""Embedding interface for chunk vectorization.

Embedder is the callable contract: takes a list of strings, returns a
list of float-vectors (one per input). Two impls ship:

  - OpenAIEmbedder    real provider; lazy-imports the openai SDK
  - FakeEmbedder      deterministic, dependency-free; for tests

Plugins that need embeddings get one via dependency injection rather
than importing OpenAI directly. That keeps the engine usable without
the OpenAI SDK installed (tests, offline dev) and makes provider swaps
a one-line change at the boundary.
"""
from __future__ import annotations

import hashlib
from typing import Protocol


class Embedder(Protocol):
    """Callable contract: list[str] → list[list[float]] (one vector per input)."""

    dim: int  # vector dimensionality

    def __call__(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """Deterministic fake — hashes each text to produce a stable vector.

    Used in tests so retrieval logic is exercisable without a real
    embedding provider. NOT for production use; vectors have no
    semantic meaning.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def __call__(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            # Take first `dim` bytes; normalize to [-1, 1] floats
            vec = [(b - 128) / 128.0 for b in digest[: self.dim]]
            # Pad with zeros if hash was too short
            while len(vec) < self.dim:
                vec.append(0.0)
            out.append(vec)
        return out


class OpenAIEmbedder:
    """OpenAI embedding-API caller. Lazy SDK import.

    Set `model` per the deployment profile (chio-developer-base defaults
    to `text-embedding-3-small`, dim=1536, per .env.example).
    """

    DEFAULT_DIMS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self.model = model
        self.dim = self.DEFAULT_DIMS.get(model, 1536)
        self._api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                import openai  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "OpenAI SDK not installed. `pip install openai` or "
                    "use FakeEmbedder for tests."
                ) from e
            self._client = openai.OpenAI(api_key=self._api_key) if self._api_key else openai.OpenAI()
        return self._client

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        response = client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in response.data]
