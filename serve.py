#!/usr/bin/env python3
"""Serve the generated dashboard. `python3 serve.py [port]` then open the URL.

site/index.html also opens fine by double-clicking; this exists for when a real
http origin is wanted.
"""

import functools
import http.server
import os
import socketserver
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    if not os.path.exists(os.path.join(ROOT, "index.html")):
        sys.exit("No dashboard yet. Run: python3 run_daily.py")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print("Dashboard: http://127.0.0.1:%d/  (ctrl-c to stop)" % port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
