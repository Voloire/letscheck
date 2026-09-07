"""Start AstroChecker on localhost, or inside a container when asked to."""

import argparse
import os
import threading
import webbrowser

from astrochecker.server import create_server


def _port_from_environment():
    raw = os.environ.get("PORT", "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        raise SystemExit("PORT must be a number") from None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Start AstroChecker locally")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="address to bind; keep the default on a desktop, use 0.0.0.0 inside a container",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_port_from_environment(),
        help="local port; 0 chooses a free port. Defaults to the PORT environment variable when set",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    parser.add_argument(
        "--public-host",
        default=os.environ.get("ASTROCHECKER_PUBLIC_HOST") or None,
        help=(
            "hostname the app is published at behind an HTTPS proxy; also read from "
            "ASTROCHECKER_PUBLIC_HOST. Turns on the stateless cloud mode"
        ),
    )
    return parser.parse_args(argv)


def display_url(host, port):
    shown = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host
    return f"http://{shown}:{port}/"


def main():
    args = parse_args()
    if not 0 <= args.port <= 65535:
        raise SystemExit("Port must be between 0 and 65535")
    server = create_server(host=args.host, port=args.port, public_host=args.public_host)
    url = display_url(args.host, server.server_port)
    print(f"AstroChecker is available at {url}", flush=True)
    if args.public_host:
        print(f"Serving the public host https://{args.public_host}/ (stateless mode)", flush=True)
    if not args.no_browser:
        opener = threading.Timer(0.4, webbrowser.open, args=(url,))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AstroChecker.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
