"""CLI: Run the full evolution loop."""

import argparse
import asyncio
import logging
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from evolution.loop import run_evolution


def main():
    parser = argparse.ArgumentParser(description="Run the full prompt evolution loop")
    parser.add_argument("--max-generations", type=int, default=10, help="Maximum generations to run")
    parser.add_argument("--threshold", type=float, default=4.0, help="Score threshold to stop at")
    parser.add_argument("--conversations-per-persona", type=int, default=3, help="Conversations per persona per generation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    champion = asyncio.run(
        run_evolution(
            max_generations=args.max_generations,
            threshold=args.threshold,
            conversations_per_persona=args.conversations_per_persona,
        )
    )

    print(f"\nChampion: {champion.id} (score: {champion.scores.aggregate:.2f})")


if __name__ == "__main__":
    main()
