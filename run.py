"""Start AstroChecker on localhost."""

import argparse
import threading
import webbrowser

from astrochecker.server import create_server


def parse_args():
    parser = argparse.ArgumentParser(description="Start AstroChecker locally")
    parser.add_argument("--port", type=int, default=0, help="local port; 0 chooses a free port")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    return parser.parse_args()


def main():
    args = parse_args()
    if not 0 <= args.port <= 65535:
        raise SystemExit("Port must be between 0 and 65535")
    server = create_server(port=args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"AstroChecker is available at {url}", flush=True)
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
