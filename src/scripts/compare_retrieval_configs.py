from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable
import pandas as pd
from memes_bot.client import build_openai_client, embed_texts
from memes_bot.config import Settings
from memes_bot.local_retrieval import embed_queries_with_local_model
from memes_bot.retriever import pick_best_meme_with_candidates, retrieve_candidates
from memes_bot.reranker import rerank_candidates_with_local_reranker
from memes_bot.vector_store import get_collection


EvalItem = dict[str, str]
Ranker = Callable[[str], list[str]]


@dataclass(frozen=True)
class RetrievalConfig:
    name: str
    retrieval_backend: str
    rerank_backend: str
    collection: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--query-columns", required=True, nargs="+")
    parser.add_argument("--id-column", default="meme_id")
    parser.add_argument("--split", default="")
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--retrieve-k", type=int, default=20)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["api-api", "api-local", "local-api", "local-local"],
        choices=[
            "api-api",
            "api-local",
            "local-api",
            "local-local",
            "api",
            "local",
            "baseline",
            "local-rerank",
            "llm-rerank",
        ],
    )
    parser.add_argument("--baseline-collection", default="")
    parser.add_argument("--api-collection", default="")
    parser.add_argument("--local-collection", default="")
    parser.add_argument("--show-failures", type=int, default=0)
    return parser.parse_args()


def load_dataframe(path: Path) -> pd.DataFrame:
    return pd.read_csv(path.resolve(), encoding="cp1251", sep=";")


def extract_query_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]

    return [text]


def build_eval_queries(
    df: pd.DataFrame,
    query_columns: list[str],
    id_column: str,
) -> list[EvalItem]:
    queries: list[EvalItem] = []
    for _, row in df.iterrows():
        meme_id = str(row.get(id_column, "")).strip()
        if not meme_id or meme_id.lower() == "nan":
            continue

        for column in query_columns:
            for query in extract_query_values(row.get(column, "")):
                queries.append(
                    {
                        "meme_id": meme_id,
                        "query": query,
                        "source_column": column,
                    }
                )
    return queries


def find_rank(candidate_ids: list[str], target_id: str) -> int | None:
    for index, candidate_id in enumerate(candidate_ids, start=1):
        if candidate_id == target_id:
            return index
    return None


def evaluate_mode(
    name: str,
    ranker: Ranker,
    queries: list[EvalItem],
    top_k: list[int],
) -> dict:
    recall_hits = {k: 0 for k in top_k}
    rank_sum = 0.0
    failures: list[dict] = []
    errors = 0

    for item in queries:
        try:
            ranked_ids = ranker(item["query"])
        except Exception as exc:
            errors += 1
            failures.append(
                {
                    "query": item["query"],
                    "meme_id": item["meme_id"],
                    "source_column": item["source_column"],
                    "error": repr(exc),
                }
            )
            continue

        rank = find_rank(ranked_ids, item["meme_id"])
        if rank is not None:
            rank_sum += 1.0 / rank
            for k in top_k:
                if rank <= k:
                    recall_hits[k] += 1
        else:
            failures.append(
                {
                    "query": item["query"],
                    "meme_id": item["meme_id"],
                    "source_column": item["source_column"],
                    "top_ids": ranked_ids[: max(top_k)],
                }
            )

    total = len(queries)
    return {
        "mode": name,
        "total": total,
        "errors": errors,
        "recall": {k: recall_hits[k] / total if total else 0.0 for k in top_k},
        "mrr": rank_sum / total if total else 0.0,
        "failures": failures,
    }


def normalize_modes(modes: list[str]) -> list[str]:
    aliases = {
        "baseline": "api",
        "llm-rerank": "local-api",
        "local-rerank": "local-local",
    }
    normalized: list[str] = []
    for mode in modes:
        resolved = aliases.get(mode, mode)
        if resolved not in normalized:
            normalized.append(resolved)
    return normalized


def build_retrieval_configs(
    modes: list[str],
    base_settings: Settings,
    api_collection: str,
    local_collection: str,
) -> list[RetrievalConfig]:
    api_collection = api_collection or base_settings.meme_collection
    local_collection = local_collection or base_settings.meme_collection

    available = {
        "api": RetrievalConfig(
            name="api",
            retrieval_backend="api",
            rerank_backend="none",
            collection=api_collection,
        ),
        "local": RetrievalConfig(
            name="local",
            retrieval_backend="local",
            rerank_backend="none",
            collection=local_collection,
        ),
        "api-api": RetrievalConfig(
            name="api-api",
            retrieval_backend="api",
            rerank_backend="api",
            collection=api_collection,
        ),
        "api-local": RetrievalConfig(
            name="api-local",
            retrieval_backend="api",
            rerank_backend="local",
            collection=api_collection,
        ),
        "local-api": RetrievalConfig(
            name="local-api",
            retrieval_backend="local",
            rerank_backend="api",
            collection=local_collection,
        ),
        "local-local": RetrievalConfig(
            name="local-local",
            retrieval_backend="local",
            rerank_backend="local",
            collection=local_collection,
        ),
    }
    return [available[mode] for mode in normalize_modes(modes)]


def make_ranker(
    config: RetrievalConfig,
    base_settings: Settings,
    retrieve_k: int,
) -> Ranker:
    if config.retrieval_backend == "local":
        _require_setting(
            base_settings.local_retrieval_model_path,
            f"LOCAL_RETRIEVAL_MODEL_PATH is required for mode '{config.name}'.",
        )
        local_retrieval_model_path = base_settings.local_retrieval_model_path
    else:
        local_retrieval_model_path = ""

    if config.rerank_backend == "local":
        _require_setting(
            base_settings.local_reranker_model_path,
            f"LOCAL_RERANKER_MODEL_PATH is required for mode '{config.name}'.",
        )
        local_reranker_model_path = base_settings.local_reranker_model_path
    else:
        local_reranker_model_path = ""

    settings = replace(
        base_settings,
        retrieval_top_k=retrieve_k,
        meme_collection=config.collection,
        local_retrieval_model_path=local_retrieval_model_path,
        local_reranker_model_path=local_reranker_model_path,
    )

    if config.rerank_backend == "api":

        def api_rerank_ranker(query: str, settings: Settings = settings) -> list[str]:
            selected, candidates = pick_best_meme_with_candidates(query, settings)
            selected_id = selected["id"]
            return [selected_id] + [
                candidate["id"]
                for candidate in candidates
                if candidate["id"] != selected_id
            ]

        return api_rerank_ranker

    if config.rerank_backend == "local":

        def local_rerank_ranker(query: str, settings: Settings = settings) -> list[str]:
            candidates = retrieve_candidates(query, settings)
            reranked = rerank_candidates_with_local_reranker(query, candidates, settings)
            return [candidate["id"] for candidate in reranked]

        return local_rerank_ranker

    def retrieval_ranker(query: str, settings: Settings = settings) -> list[str]:
        return [candidate["id"] for candidate in retrieve_candidates(query, settings)]

    return retrieval_ranker


def make_rankers(args: argparse.Namespace, base_settings: Settings) -> dict[str, Ranker]:
    api_collection = (
        args.api_collection
        or args.baseline_collection
        or base_settings.meme_collection
    )
    configs = build_retrieval_configs(
        modes=args.modes,
        base_settings=base_settings,
        api_collection=api_collection,
        local_collection=args.local_collection,
    )
    return {
        config.name: make_ranker(config, base_settings, args.retrieve_k)
        for config in configs
    }


def compare_model_metrics(
    queries: list[EvalItem],
    settings: Settings,
    top_k: list[int],
    retrieve_k: int,
    modes: list[str] | None = None,
    api_collection: str = "",
    local_collection: str = "",
) -> list[dict]:
    configs = build_retrieval_configs(
        modes=modes or ["api-api", "api-local", "local-api", "local-local"],
        base_settings=settings,
        api_collection=api_collection,
        local_collection=local_collection,
    )
    validate_collections(configs, settings, queries[0]["query"])
    return [
        evaluate_mode(
            name=config.name,
            ranker=make_ranker(config, settings, retrieve_k),
            queries=queries,
            top_k=top_k,
        )
        for config in configs
    ]


def validate_collections(
    configs: list[RetrievalConfig],
    settings: Settings,
    sample_query: str,
) -> None:
    checked: set[str] = set()
    for config in configs:
        check_key = f"{config.retrieval_backend}:{config.collection}"
        if check_key in checked:
            continue
        checked.add(check_key)
        collection = get_collection(settings.chroma_dir, config.collection)
        count = collection.count()
        if count == 0:
            raise RuntimeError(
                "Chroma collection "
                f"'{config.collection}' is empty. Reindex it before comparing "
                f"mode '{config.name}'."
            )
        expected_dim = get_query_embedding_dimension(
            backend=config.retrieval_backend,
            settings=settings,
            sample_query=sample_query,
        )
        actual_dim = get_collection_embedding_dimension(collection)
        if actual_dim != expected_dim:
            raise RuntimeError(
                f"Chroma collection '{config.collection}' has {actual_dim}-dim "
                f"embeddings, but mode '{config.name}' uses "
                f"{config.retrieval_backend} retrieval with {expected_dim}-dim "
                "query embeddings. Reindex this collection with the same "
                "embedding backend used by the mode."
            )


def get_query_embedding_dimension(
    backend: str,
    settings: Settings,
    sample_query: str,
) -> int:
    if backend == "local":
        embedding = embed_queries_with_local_model([sample_query], settings)[0]
        return len(embedding)

    client = build_openai_client(settings)
    embedding = embed_texts(client, settings.openai_embedding_model, [sample_query])[0]
    return len(embedding)


def get_collection_embedding_dimension(collection: object) -> int:
    data = collection.get(limit=1, include=["embeddings"])
    embeddings = data.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        raise RuntimeError(f"Could not read embeddings from '{collection.name}'.")
    return len(embeddings[0])


def _require_setting(value: str, message: str) -> None:
    if not value.strip():
        raise RuntimeError(message)


def print_results(results: list[dict], top_k: list[int]) -> None:
    headers = ["mode", "queries", "errors", *[f"Recall@{k}" for k in top_k], "MRR"]
    rows = []
    for result in results:
        rows.append(
            [
                result["mode"],
                str(result["total"]),
                str(result["errors"]),
                *[f"{result['recall'][k]:.4f}" for k in top_k],
                f"{result['mrr']:.4f}",
            ]
        )

    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def print_failures(results: list[dict], limit: int) -> None:
    if limit == 0:
        return

    for result in results:
        failures = result["failures"] if limit == -1 else result["failures"][:limit]
        if not failures:
            continue
        print(f"\nfailures for {result['mode']}:")
        for failure in failures:
            print(json.dumps(failure, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    df = load_dataframe(Path(args.dataset))
    if args.split:
        df = df[df["split"].astype(str).str.lower() == args.split.lower()].copy()

    queries = build_eval_queries(df, args.query_columns, args.id_column)
    if not queries:
        raise RuntimeError("No evaluation queries found.")

    top_k = sorted(args.top_k)
    api_collection = (
        args.api_collection
        or args.baseline_collection
        or settings.meme_collection
    )
    results = compare_model_metrics(
        queries=queries,
        settings=settings,
        top_k=top_k,
        retrieve_k=args.retrieve_k,
        modes=args.modes,
        api_collection=api_collection,
        local_collection=args.local_collection,
    )

    print_results(results, top_k)
    print_failures(results, args.show_failures)


if __name__ == "__main__":
    main()