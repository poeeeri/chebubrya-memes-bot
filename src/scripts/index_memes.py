from __future__ import annotations

import argparse
from dataclasses import replace
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
        "--collection",
        default="",
        help="Chroma collection name. Defaults to MEME_COLLECTION.",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["env", "api", "local"],
        default="env",
        help="Use API embeddings, local embeddings, or current env settings.",
    )
    parser.add_argument(
        "--reset",
        action="store_true"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    if args.collection:
        settings = replace(settings, meme_collection=args.collection)
    if args.embedding_backend == "api":
        settings = replace(settings, local_retrieval_model_path="")
    elif args.embedding_backend == "local":
        if not settings.local_retrieval_model_path:
            raise RuntimeError(
                "LOCAL_RETRIEVAL_MODEL_PATH is required for --embedding-backend local."
            )
    indexed_count = index_meme(
        dataset_path=Path(args.dataset),
        image_column=args.image_column,
        text_columns=args.text_columns,
        settings=settings,
        reset=args.reset,
    )
    backend = "local" if settings.local_retrieval_model_path else "api"
    print(
        f"indexed {indexed_count} memes into "
        f"'{settings.meme_collection}' with {backend} embeddings."
    )


if __name__ == "__main__":
    main()