"""CLI: Generate HTML evolution report."""

import logging
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from dashboard.report_generator import generate_report


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    path = generate_report()
    print(f"Report generated: {path}")


if __name__ == "__main__":
    main()
