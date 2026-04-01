from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--rows",
        type=int,
        default=5,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset)
    df = pd.read_csv(dataset_path, encoding='cp1251', sep=';')

    print("columns:")
    for column in df.columns:
        print(f"- {column}")

    print("\npreview:")
    print(df.head(args.rows).to_string(index=False))


if __name__ == "__main__":
    main()