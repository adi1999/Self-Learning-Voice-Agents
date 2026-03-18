"""CLI: Simulate one version against all personas."""

import argparse
import asyncio
import logging
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from core.archive import load_version, save_conversation
from simulation.persona_runner import run_full_evaluation_suite


def main():
    parser = argparse.ArgumentParser(description="Simulate one version against all personas")
    parser.add_argument("--version", required=True, help="Version ID (e.g., v0)")
    parser.add_argument("--conversations-per-persona", type=int, default=3)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    version = load_version(args.version)
    conversations = asyncio.run(
        run_full_evaluation_suite(version, args.conversations_per_persona)
    )

    for conv in conversations:
        save_conversation(conv)
        print(f"  {conv.id}: {conv.outcome} ({conv.duration_turns} turns)")

    print(f"\nSaved {len(conversations)} conversations")


if __name__ == "__main__":
    main()
