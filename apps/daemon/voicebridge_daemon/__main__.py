from __future__ import annotations

import argparse

import uvicorn

from voicebridge_daemon.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="VoiceBridge daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

