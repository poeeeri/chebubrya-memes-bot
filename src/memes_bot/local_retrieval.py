from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

from sentence_transformers import SentenceTransformer

from .config import ROOT_DIR, Settings


def _resolve_model_path(model_path: str) -> Path:
    path = Path(model_path).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


def prefix_query(text: str, settings: Settings) -> str:
    return f"query: {text}" if settings.local_retrieval_use_e5_prefixes else text


def prefix_passage(text: str, settings: Settings) -> str:
    return f"passage: {text}" if settings.local_retrieval_use_e5_prefixes else text


def embed_queries_with_local_model(texts: Iterable[str], settings: Settings) -> list[list[float]]:
    prefixed_texts = [prefix_query(text, settings) for text in texts]
    return _embed_texts(prefixed_texts, settings.local_retrieval_model_path)


def embed_passages_with_local_model(texts: Iterable[str], settings: Settings) -> list[list[float]]:
    prefixed_texts = [prefix_passage(text, settings) for text in texts]
    return _embed_texts(prefixed_texts, settings.local_retrieval_model_path)


def _embed_texts(texts: list[str], model_path: str) -> list[list[float]]:
    if not model_path.strip():
        raise ValueError("LOCAL_RETRIEVAL_MODEL_PATH is empty.")

    model = load_local_retrieval_model(model_path)
    embeddings = model.encode(
        texts,
        batch_size=64,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.astype(float).tolist()


@lru_cache(maxsize=1)
def load_local_retrieval_model(model_path: str) -> SentenceTransformer:
    resolved = _resolve_model_path(model_path)
    if not (resolved / "modules.json").exists():
        raise FileNotFoundError(
            f"SentenceTransformer model was not found at {resolved}")
    return SentenceTransformer(str(resolved))