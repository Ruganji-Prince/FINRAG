import hashlib
import re
from functools import lru_cache

import numpy as np

from backend.config import settings

DIM = 384
STOP = set(
    [
        "what",
        "which",
        "how",
        "when",
        "where",
        "who",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "of",
        "in",
        "to",
        "and",
        "for",
        "at",
        "on",
        "by",
        "from",
        "report",
        "according",
        "does",
        "did",
        "with",
        "about",
        "rwanda",
    ]
)


def tokens(text):
    return [
        t
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if t not in STOP and len(t) > 1
    ]


@lru_cache(maxsize=1)
def model():
    from sentence_transformers import SentenceTransformer

    loaded = SentenceTransformer(
        settings.embedding_model,
        revision=settings.embedding_revision or None,
        cache_folder=str(
            __import__("pathlib").Path(__file__).resolve().parents[1] / ".models"
        ),
        trust_remote_code=False,
        device="cpu",
    )
    if loaded.get_embedding_dimension() != DIM:
        raise ValueError("The database requires 384-dimensional embeddings")
    return loaded


def identity():
    return (
        (settings.embedding_model + "@" + settings.embedding_revision)
        if settings.embedding_backend == "sentence-transformers"
        else "lexical-hash-v1-384"
    )


def embed(texts):
    if settings.embedding_backend == "sentence-transformers":
        vectors = model().encode(
            texts,
            normalize_embeddings=True,
            batch_size=settings.embedding_batch_size,
            show_progress_bar=False,
        )
        if (
            vectors.ndim != 2
            or vectors.shape[1] != DIM
            or not np.isfinite(vectors).all()
        ):
            raise ValueError("Invalid semantic embeddings")
        return vectors.tolist()
    if settings.embedding_backend != "hash":
        raise ValueError("Unknown embedding backend")
    result = []
    for text in texts:
        row = np.zeros(DIM)
        for token in tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            row[int.from_bytes(digest[:4], "big") % DIM] += 1 if digest[4] % 2 else -1
        norm = np.linalg.norm(row)
        result.append((row / norm if norm else row).tolist())
    return result
