from __future__ import annotations
from .config import Settings
from pathlib import Path
from functools import lru_cache
from sentence_transformers import CrossEncoder


def build_candidate_text(candidate: dict) -> str:
    text_fields = []
    for key in [
        "embedding_text",
        "semantic_description",
        "ocr_text",
        "user_messages"
    ]:
        value = str(candidate.get(key, '')).strip()
        if value and value.lower != 'nan':
            text_fields.append(f'{key}: {value}')
    return " | ".join(text_fields) if text_fields else candidate.get('ocr_text', '')


def rerank_candidates_with_local_reranker(query: str, candidates: list[dict], settings: Settings) -> list[dict]:
    model_path = settings.local_reranker_model_path.strip()
    if not model_path:
        return candidates
    
    model = load_local_reranker(model_path)
    candidate_texts = [build_candidate_text(candidate) for candidate in candidates]
    pairs = [[query, text] for text in candidate_texts]
    scores = model.predict(pairs)

    reranked = []
    for candidate, score in zip(candidates, scores):
        candidate_copy = dict(candidate)
        candidate_copy['reranker_score'] = float(score)
        reranked.append(candidate_copy)
    reranked.sort(key=lambda item: item['reranker_score'], reverse=True)
    return reranked


@lru_cache(maxsize=2)
def load_local_reranker(model_path: str) -> CrossEncoder:
    resolved = Path(model_path).expanduser().resolve()
    return CrossEncoder(str(resolved), num_labels=1, max_length=512)