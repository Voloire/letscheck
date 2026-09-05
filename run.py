"""Start AstroChecker on localhost."""

import argparse
import threading
import webbrowser

from astrochecker.server import create_server


def parse_args():
    parser = argparse.ArgumentParser(description="Avvia AstroChecker in locale")
    parser.add_argument("--port", type=int, default=0, help="porta locale; 0 sceglie una porta libera")
    parser.add_argument("--no-browser", action="store_true", help="non aprire automaticamente il browser")
    return parser.parse_args()


def main():
    args = parse_args()
    if not 0 <= args.port <= 65535:
        raise SystemExit("La porta deve essere compresa tra 0 e 65535")
    server = create_server(port=args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"AstroChecker disponibile su {url}", flush=True)
    if not args.no_browser:
        opener = threading.Timer(0.4, webbrowser.open, args=(url,))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto AstroChecker.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
