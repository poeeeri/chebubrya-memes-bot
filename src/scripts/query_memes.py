from __future__ import annotations

import argparse
import sys
from pathlib import Path

from memes_bot.config import Settings
from memes_bot.retriever import pick_best_meme_with_candidates, retrieve_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--show-candidates",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings.from_env()
    print(
        (
            f"collection={settings.meme_collection} "
            f"chroma_dir={settings.chroma_dir} "
            f"top_k={settings.retrieval_top_k}"
        ),
        file=sys.stderr,
        flush=True,
    )
    print("retrieving candidates...", file=sys.stderr, flush=True)

    if args.show_candidates:
        candidates = retrieve_candidates(args.query, settings)
        print(f"found candidates: {len(candidates)}", file=sys.stderr, flush=True)
        for candidate in candidates:
            print(candidate)
        return

    print("picking best meme...", file=sys.stderr, flush=True)
    best, candidates = pick_best_meme_with_candidates(args.query, settings)
    print(f"found candidates: {len(candidates)}", file=sys.stderr, flush=True)
    image_path = Path(str(best.get("image_path", "")))
    print(f"image exists: {image_path.exists()} path={image_path}", file=sys.stderr, flush=True)
    print(best)


if __name__ == "__main__":
    main()