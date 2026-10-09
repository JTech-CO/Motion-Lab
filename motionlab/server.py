"""Loopback-only, read-only HTTP API and constrained static-file server."""

from collections import deque
import json
import mimetypes
from pathlib import Path
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from .catalog import Catalog, CatalogUnavailable
from .validation import ValidationError
from .analysis_schema import ANALYSIS_FILTERS

CSP = "; ".join(("default-src 'self'", "script-src 'self'", "style-src 'self' 'unsafe-inline'",
                  "img-src 'self' data:", "font-src 'self'", "connect-src 'self'", "frame-src 'self'",
                  "object-src 'none'", "base-uri 'none'", "form-action 'none'", "frame-ancestors 'none'"))
STATIC_TYPES = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff2", ".txt"}


class RateLimiter:
    def __init__(self, limit=120, window=60):
        self.limit = limit
        self.window = window
        self.events = {}
        self.lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self.lock:
            events = self.events.setdefault(key, deque())
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def static_path(root, url_path):
    """Resolve once, reject traversal, hidden paths, and unsupported file types."""
    decoded = unquote(url_path, errors="strict")
    if "\x00" in decoded or "\\" in decoded or ":" in decoded:
        raise ValidationError("Invalid static path")
    parts = decoded.split("/")
    if any(part.startswith(".") for part in parts if part):
        raise ValidationError("Invalid static path")
    root = Path(root).resolve()
    path = (root / (decoded.lstrip("/") or "index.html")).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValidationError("Invalid static path") from error
    if path.suffix.lower() not in STATIC_TYPES or not path.is_file():
        return None
    return path


def make_server(root, port=8787, host="127.0.0.1"):
    if host not in ("127.0.0.1", "localhost"):
        raise ValidationError("The local server binds only to 127.0.0.1 or localhost")
    catalog = Catalog(root)
    # Fail before accepting requests if no database has been built.
    catalog.stats()
    static_root = Path(root).resolve() / "dist"
    limiter = RateLimiter()

    class Handler(BaseHTTPRequestHandler):
        server_version = "MotionLab"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_args):
            # No persistent IP/search logs or personal-data collection.
            pass

        def respond(self, status, body, content_type="application/json; charset=utf-8", extra=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            self.send_header("Cache-Control", "no-cache")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def error(self, status, message):
            self.respond(status, {"error": message})

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
                if self.headers.get("Host", "").lower() not in allowed_hosts:
                    self.error(403, "Host is not allowed")
                    return
                origin = self.headers.get("Origin")
                if origin and origin not in {"http://" + entry for entry in allowed_hosts}:
                    self.error(403, "Origin is not allowed")
                    return
                if len(self.path) > 8192:
                    self.error(414, "Request URI is too long")
                    return
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc:
                    self.error(400, "Invalid request target")
                    return
                if parsed.path.startswith("/api/"):
                    if not limiter.allow(self.client_address[0]):
                        self.respond(429, {"error": "Rate limit exceeded"}, extra={"Retry-After": "60"})
                        return
                    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=13)
                    if any(len(values) != 1 for values in query.values()):
                        raise ValidationError("Query parameters cannot repeat")
                    if parsed.path == "/api/search":
                        allowed = {"q", "category", "license", "kind", "limit", "offset", *ANALYSIS_FILTERS}
                        if set(query) - allowed:
                            raise ValidationError("Unsupported query parameter")
                        args = {("query" if key == "q" else key): values[0] for key, values in query.items()}
                        for name in ("limit", "offset"):
                            if name in args:
                                if not args[name].isascii() or not args[name].isdigit() or len(args[name]) > 6:
                                    raise ValidationError(f"{name} must be a bounded integer")
                                args[name] = int(args[name])
                        self.respond(200, catalog.search(**args))
                    elif parsed.path == "/api/stats":
                        if query:
                            raise ValidationError("stats accepts no arguments")
                        self.respond(200, catalog.stats())
                    elif parsed.path.startswith("/api/items/"):
                        if query:
                            raise ValidationError("get item accepts no query arguments")
                        item = catalog.get(unquote(parsed.path[len("/api/items/"):], errors="strict"))
                        self.respond(200, item) if item else self.error(404, "Item not found")
                    else:
                        self.error(404, "Endpoint not found")
                    return
                if parsed.query:
                    # Static asset query cache keys are harmless; no dynamic interpretation.
                    pass
                path = static_path(static_root, parsed.path)
                if path is None:
                    self.error(404, "File not found")
                    return
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                if path.suffix in (".html", ".css", ".js", ".json", ".txt"):
                    content_type += "; charset=utf-8"
                self.respond(200, path.read_bytes(), content_type)
            except (ValidationError, ValueError, UnicodeError):
                self.error(400, "Invalid request arguments")
            except CatalogUnavailable:
                self.error(503, "Catalog unavailable")
            except (OSError, RuntimeError, sqlite3.Error):
                self.error(500, "Request failed")

        def reject_write(self):
            self.respond(405, {"error": "Read-only service"}, extra={"Allow": "GET, HEAD"})

        do_POST = reject_write
        do_PUT = reject_write
        do_PATCH = reject_write
        do_DELETE = reject_write
        do_OPTIONS = reject_write

    return ThreadingHTTPServer((host, port), Handler)


def serve(root, port=8787, host="127.0.0.1"):
    server = make_server(root, port, host)
    print(f"Motion Lab: http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
