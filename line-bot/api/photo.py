"""照片代理端點：LINE 伺服器透過此端點取 Google Places 照片，避免 referrer 限制。"""
from __future__ import annotations

import os
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


GKEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
PHOTO_BASE = "https://maps.googleapis.com/maps/api/place/photo"


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        qs = parse_qs(urlparse(self.path).query)
        ref = (qs.get("ref") or qs.get("r") or [""])[0]

        if not ref or not GKEY:
            self.send_error(400, "missing ref or key")
            return

        url = f"{PHOTO_BASE}?maxwidth=400&photo_reference={ref}&key={GKEY}"
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=5)
            body = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(502, str(e)[:100])

    def log_message(self, *args):  # noqa: D401
        pass
