from __future__ import annotations
import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Callable
import pandas as pd
from memes_bot.config import Settings
from memes_bot.retriever import pick_best_meme_with_candidates, retrieve_candidates
from memes_bot.reranker import rerank_candidates_with_local_reranker


EvalItem = dict[str, str]
Ranker = Callable[[str], list[str]]


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
        default=["baseline", "local", "local-rerank", "llm-rerank"],
        choices=["baseline", "local", "local-rerank", "llm-rerank"],
    )
    parser.add_argument("--baseline-collection", default="")
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


def make_rankers(args: argparse.Namespace, base_settings: Settings) -> dict[str, Ranker]:
    baseline_collection = args.baseline_collection or base_settings.meme_collection
    local_collection = args.local_collection or base_settings.meme_collection
    rankers: dict[str, Ranker] = {}

    if "baseline" in args.modes:
        settings = replace(
            base_settings,
            retrieval_top_k=args.retrieve_k,
            meme_collection=baseline_collection,
            local_retrieval_model_path="",
            local_reranker_model_path="",
        )

        def baseline_ranker(query: str, settings: Settings = settings) -> list[str]:
            return [candidate["id"] for candidate in retrieve_candidates(query, settings)]

        rankers["baseline"] = baseline_ranker

    if "local" in args.modes:
        _require_setting(
            base_settings.local_retrieval_model_path,
            "LOCAL_RETRIEVAL_MODEL_PATH is required for mode 'local'.",
        )
        settings = replace(
            base_settings,
            retrieval_top_k=args.retrieve_k,
            meme_collection=local_collection,
            local_reranker_model_path="",
        )

        def local_ranker(query: str, settings: Settings = settings) -> list[str]:
            return [candidate["id"] for candidate in retrieve_candidates(query, settings)]

        rankers["local"] = local_ranker

    if "local-rerank" in args.modes:
        _require_setting(
            base_settings.local_retrieval_model_path,
            "LOCAL_RETRIEVAL_MODEL_PATH is required for mode 'local-rerank'.",
        )
        _require_setting(
            base_settings.local_reranker_model_path,
            "LOCAL_RERANKER_MODEL_PATH is required for mode 'local-rerank'.",
        )
        settings = replace(
            base_settings,
            retrieval_top_k=args.retrieve_k,
            meme_collection=local_collection,
        )

        def local_rerank_ranker(query: str, settings: Settings = settings) -> list[str]:
            candidates = retrieve_candidates(query, settings)
            reranked = rerank_candidates_with_local_reranker(query, candidates, settings)
            return [candidate["id"] for candidate in reranked]

        rankers["local-rerank"] = local_rerank_ranker

    if "llm-rerank" in args.modes:
        settings = replace(
            base_settings,
            retrieval_top_k=args.retrieve_k,
            meme_collection=local_collection,
            local_reranker_model_path="",
        )

        def llm_rerank_ranker(query: str, settings: Settings = settings) -> list[str]:
            selected, candidates = pick_best_meme_with_candidates(query, settings)
            selected_id = selected["id"]
            return [selected_id] + [
                candidate["id"]
                for candidate in candidates
                if candidate["id"] != selected_id
            ]

        rankers["llm-rerank"] = llm_rerank_ranker

    return rankers


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
    rankers = make_rankers(args, settings)
    results = [
        evaluate_mode(name, ranker, queries, top_k)
        for name, ranker in rankers.items()
    ]

    print_results(results, top_k)
    print_failures(results, args.show_failures)


if __name__ == "__main__":
    main()