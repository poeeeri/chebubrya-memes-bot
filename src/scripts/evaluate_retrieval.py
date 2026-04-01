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
    return pd.read_csv(resolved_path)


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
    runk_sum = 0.0
    failures: list[dict] = []


if __name__=='__main__':
    main()