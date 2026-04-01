from __future__ import annotations
import argparse
import json
from memes_bot.config import Settings
import pandas as pd
from pathlib import Path
from memes_bot.retriever import retrieve_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--query-columns', required=True, nargs='+')
    parser.add_argument('--id-column', default='meme_id')
    parser.add_argument('--split', default='')
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument('--show-failure', type=int, nargs='+', default=20)
    return parser.parse_args()


def load_dataframe(path: Path) -> pd.DataFrame:
    resolved_path = path.resolve()
    return pd.read_csv(resolved_path, encoding='cp1251', sep=';')


def extract_query_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]

    return [text]


def build_eval_queries(df: pd.DataFrame, query_columns: list[str], id_column: str) -> list[dict]:
    queries: list[dict] = []
    for _, row in df.iterrows():
        meme_id = str(row.get(id_column, '')).strip()
        if not meme_id:
            continue

        for column in query_columns:
            values = extract_query_values(row.get(column, ''))
            for v in values:
                queries.append({
                    'meme_id': meme_id,
                    'query': v,
                    'source_column': column
                })
    return queries


def find_rank(candidate_ids: list[str], target_id: str) -> int | None:
    for index, candidate_id in enumerate(candidate_ids, start=1):
        if candidate_id == target_id:
            return index
    return None


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    df = load_dataframe(Path(args.dataset))

    queries = build_eval_queries(df, args.query_columns, args.id_column)

    if not queries:
        raise RuntimeError('check dataset, (queries)')
    
    top_k = sorted(args.top_k)
    max_k = max(top_k)
    recall_hits = {k: 0 for k in top_k}
    rank_sum = 0.0
    failures: list[dict] = []

    for item in queries:
        candidates = retrieve_candidates(item['query'], settings, max_k)
        candidate_ids = [candidate['id'] for candidate in candidates]
        rank = find_rank(candidate_ids, item['meme_id'])

        if rank is not None:
            rank_sum += 1.0 / rank
            for k in top_k:
                if rank <= k:
                    recall_hits[k] += 1
        else:
            failures.append({
                'query': item['query'],
                'meme_id': item['meme_id'],
                'source_column': item['source_column'],
                'top_ids': candidate_ids
            })
    
    total = len(queries)
    print('count of queries:', total)
    for k in top_k:
        print(f'recall@{k}: {recall_hits[k] / total:.4f} ({recall_hits[k]}/{total})')
    print(f"MRR: {rank_sum / total:.4f}")

    if failures and args.show_failures > 0:
        print("\nfailures:")
        for failure in failures[: args.show_failures]:
            print(json.dumps(failure, ensure_ascii=False))


if __name__=='__main__':
    main()