from __future__ import annotations
from .config import Settings
from .vector_store import get_collection
from .client import build_openai_client, embed_texts, choose_best_meme


def retrieve_candidates(query: str, settings: Settings, n_results: int) -> list[dict]:
    collection = get_collection(settings.chroma_dir, settings.meme_collection)
    client = build_openai_client(settings)
# получаем эмюеддинг запроса пользователя
    query_embed = embed_texts(
        client,
        settings.openai_embedding_model,
        [query]
    )[0]

# поиск эьмеддингов мемов в векторной бд
    result = collection.query(
        query_embeddings=[query_embed],
        n_results=n_results or settings.retrieval_top_k
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    candidates = []
    for meme_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        candidates.append(
            {
                "id": meme_id,
                "summary": metadata.get("summary", document),
                "image_path": metadata["image_path"],
                "distance": distance,
            }
        )

    return candidates


def pick_best_meme(query: str, settings: Settings) -> dict:
    candidates = retrieve_candidates(query, settings)
    client = build_openai_client(settings)
    choice = choose_best_meme(
        client=client,
        model=settings.openai_rerank_model,
        query=query,
        candidates=candidates,
    )

    chosen_id = choice.get("meme_id")

    for candidate in candidates:
        if candidate["id"] == chosen_id:
            candidate["reason"] = choice.get("reason", "")
            return candidate
        
    fallback = candidates[0]
    fallback["reason"] = "выбранный meme_id не найден."
    return fallback