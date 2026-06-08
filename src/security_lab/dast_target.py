from __future__ import annotations

import argparse
from html import escape
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class DastTargetHandler(BaseHTTPRequestHandler):
    server_version = "memes-bot"
    sys_version = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html("<!doctype html><html><body>Security lab target</body></html>")
            return

        if parsed.path == "/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "chebubrya-memes-bot",
                }
            )
            return

        if parsed.path == "/robots.txt":
            self._send_text("User-agent: *\nDisallow:\n")
            return

        if parsed.path == "/sitemap.xml":
            self._send_xml(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>http://localhost:8080/health</loc></url>"
                "</urlset>"
            )
            return

        if parsed.path == "/echo":
            query = parse_qs(parsed.query).get("q", [""])[0]
            if not getattr(self.server, "vulnerable", False):
                query = escape(query)
            self._send_html(f"<html><body>echo: {query}</body></html>")
            return

        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def end_headers(self) -> None:
        if not getattr(self.server, "vulnerable", False):
            self._send_security_headers()
        super().end_headers()

    def version_string(self) -> str:
        if getattr(self.server, "vulnerable", False):
            return "MemesBotSecurityLab/1.0 Python/3.12.0"
        return self.server_version

    def _send_json(self, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body_text: str) -> None:
        body = body_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, body_text: str) -> None:
        body = body_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_xml(self, body_text: str) -> None:
        body = body_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; "
            "script-src 'none'; "
            "style-src 'none'; "
            "img-src 'none'; "
            "font-src 'none'; "
            "connect-src 'none'; "
            "media-src 'none'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "worker-src 'none'; "
            "manifest-src 'none'; "
            "base-uri 'none'; "
            "form-action 'none'; "
            "frame-ancestors 'none'",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--vulnerable",
        "--vulnerability",
        "--vulnurability",
        dest="vulnerable",
        action="store_true",
        help="Run an intentionally weak endpoint for scanner demonstration.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DastTargetHandler)
    server.vulnerable = args.vulnerable
    print(f"DAST target listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
