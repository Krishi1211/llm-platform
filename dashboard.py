import json
import os
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import analytics
import alerts

HERE = os.path.dirname(os.path.abspath(__file__))


def _hours(query):
    try:
        return max(1, min(int(query.get("hours", ["24"])[0]), 24 * 90))
    except ValueError:
        return 24


def api(path, query):
    hours = _hours(query)
    if path == "/api/summary":
        return analytics.summary(hours)
    if path == "/api/models":
        return analytics.by_model(hours)
    if path == "/api/timeseries":
        return analytics.timeseries(hours, "day" if hours > 72 else "hour")
    if path == "/api/tags":
        return analytics.by_tag(query.get("tag", ["feature"])[0], hours)
    if path == "/api/recent":
        return analytics.recent()
    if path == "/api/alerts":
        alerts.check_alerts()
        return alerts.recent_alerts()
    return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            with open(os.path.join(HERE, "dashboard.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        try:
            data = api(url.path, parse_qs(url.query))
        except Exception as e:
            return self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")
        if data is None:
            return self._send(404, b'{"error": "not found"}', "application/json")
        self._send(200, json.dumps(data).encode(), "application/json")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Helix cost analytics dashboard")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    alerts.create_tables()
    print(f"Helix dashboard on http://localhost:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
