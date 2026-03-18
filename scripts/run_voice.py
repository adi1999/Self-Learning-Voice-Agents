"""CLI: Start voice agent with a specific prompt version."""

import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Start voice agent with a specific version")
    parser.add_argument("--version", default=None, help="Version ID (e.g., v5). Uses champion if not specified.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn
    from voice.run_voice import create_app

    app = create_app(args.version)
    print(f"Starting voice agent on http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
