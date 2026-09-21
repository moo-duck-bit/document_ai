# -*- coding: utf-8 -*-
"""Launch Document AI Pilot UI (local).

  python scripts/run_pilot_ui.py
  # then open http://127.0.0.1:8765

  Docker:
  docker compose up --build
  # LAN: http://<host-ip>:8765
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Document AI Pilot UI")
    parser.add_argument(
        "--host",
        default=os.environ.get("PILOT_HOST", "127.0.0.1"),
        help="Bind address (0.0.0.0 for Docker/LAN)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PILOT_PORT", "8765")),
    )
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "uvicorn/fastapi required. Install: pip install fastapi uvicorn python-multipart"
        ) from exc

    print(f"Document AI Pilot UI → http://{args.host}:{args.port}")
    if args.host in ("0.0.0.0", "::"):
        print("WARNING: bound on all interfaces, no auth. Use only on trusted LAN/VPN.")

    uvicorn.run(
        "document_ai.pilot_ui.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
