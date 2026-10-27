"""Embeddings behind an interface.

The default `HashingEmbedder` is local, free and deterministic (feature hashing over words and
bigrams), which keeps the demo offline and tests stable. In production you'd plug in a hosted
embedding model (OpenAI text-embedding-3-small, Azure OpenAI, Bedrock Titan) by implementing
`Embedder` and matching EMBED_DIM in the pgvector column.
"""

import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.models import EMBED_DIM

STOPWORDS = set(
    "a an the and or of to in on for is are was were be been it this that with as at by from can "
    "i you we they he she my our your what how when where which who do does did not no if will".split()
    # domain words that appear in every document carry no signal
    + "policy policies company employee employees please".split()
)


SUFFIXES = ("ations", "ation", "ings", "ing", "ments", "ment", "ers", "er", "ed", "es", "s")


def stem(word: str) -> str:
    """Tiny suffix-stripping stemmer: travelling/travel, reimbursements/reimburse, claims/claim."""
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)]
            break
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]  # travell -> travel
    return word


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder(Embedder):
    dim = EMBED_DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = tokenize(text)
        # Unigrams carry the signal; bigrams add a little phrase sensitivity.
        features = [(t, 1.0) for t in tokens] + [(f"{a}_{b}", 0.5) for a, b in zip(tokens, tokens[1:], strict=False)]
        for f, weight in features:
            h = int(hashlib.md5(f.encode(), usedforsecurity=False).hexdigest(), 16)
            vec[h % self.dim] += weight if (h >> 8) & 1 else -weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))  # vectors are L2-normalised


embedder: Embedder = HashingEmbedder()
