"""CLI: Re-evaluate existing conversation logs."""

import argparse
import asyncio
import logging
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from core.archive import load_conversations, load_version, save_conversation, save_version
from evaluation.scorer import evaluate_all


def main():
    parser = argparse.ArgumentParser(description="Evaluate existing conversation logs")
    parser.add_argument("--version", required=True, help="Version ID (e.g., v0)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    version = load_version(args.version)
    conversations = load_conversations(args.version)

    if not conversations:
        print(f"No conversations found for {args.version}")
        return

    scores = asyncio.run(evaluate_all(conversations))
    version.scores = scores
    save_version(version)

    for conv in conversations:
        save_conversation(conv)

    print(f"\nScores for {args.version}:")
    print(f"  Aggregate: {scores.aggregate:.2f}")
    for persona, ms in scores.per_persona.items():
        print(f"  {persona}: goal={ms.goal_completion:.1f} quality={ms.conversational_quality:.1f} "
              f"compliance={ms.compliance:.1f} total={ms.weighted_total:.2f}")


if __name__ == "__main__":
    main()
