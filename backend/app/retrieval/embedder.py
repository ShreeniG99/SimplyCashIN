import hashlib
import math
from typing import Protocol

EMBED_DIM = 384


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class StubEmbedder:
    """Deterministic bag-of-tokens hashing embedder. Good enough for M1 retrieval;
    swap for a real sentence-transformer (same dim) in a later milestone."""

    dim = EMBED_DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
