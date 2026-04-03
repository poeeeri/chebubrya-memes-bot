from __future__ import annotations

import argparse

from memes_bot.config import Settings
from memes_bot.retriever import pick_best_meme, retrieve_candidates


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

    if args.show_candidates:
        candidates = retrieve_candidates(args.query, settings)
        for candidate in candidates:
            print(candidate)
        return

    best = pick_best_meme(args.query, settings)
    print(best)


if __name__ == "__main__":
    main()