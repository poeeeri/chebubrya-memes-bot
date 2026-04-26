from __future__ import annotations

import argparse
from pathlib import Path

from memes_bot.config import Settings
from memes_bot.indexer import index_meme


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--image-column",
        required=True,
    )
    parser.add_argument(
        "--text-columns",
        required=True,
        nargs="+",
    )
    parser.add_argument(
        "--reset",
        action="store_true"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    indexed_count = index_meme(
        dataset_path=Path(args.dataset),
        image_column=args.image_column,
        text_columns=args.text_columns,
        settings=settings,
        reset=args.reset,
    )
    print(f"indexed {indexed_count} memes.")


if __name__ == "__main__":
    main()