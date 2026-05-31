#!/usr/bin/env python3
"""Local deployment server for the cashflow system.

Serves the static application and a small REST table API compatible with
`tables/structured_finance_assets`.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import posixpath
import threading
import time
import urllib.parse
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "structured_finance_assets.json"
TABLE_PATH = "/tables/structured_finance_assets"
DATA_LOCK = threading.RLock()


def load_rows() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        backup = DATA_FILE.with_suffix(f".corrupt-{int(time.time())}.json")
        DATA_FILE.replace(backup)
        return []


def save_rows(rows: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)


def filter_asset_rows(rows: list[dict], model_id: str = "", q: str = "", search: str = "") -> list[dict]:
    """Filter rows using explicit model/query params, with legacy search support."""
    filtered = rows

    legacy_search = (search or "").strip()
    if legacy_search.startswith("modelId:") and not model_id:
        model_id = legacy_search.split(":", 1)[1]
        legacy_search = ""
    elif legacy_search and not q:
        q = legacy_search

    if model_id:
        filtered = [row for row in filtered if str(row.get("modelId", "")) == model_id]

    needle = (q or "").strip().lower()
    if needle:
        filtered = [
            row
            for row in filtered
            if needle in json.dumps(row, ensure_ascii=False).lower()
        ]

    return filtered


class CashflowHandler(BaseHTTPRequestHandler):
    server_version = "CashflowDeploy/1.0"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == TABLE_PATH:
            self.handle_table_list(parsed)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == f"{TABLE_PATH}/batch":
            self.create_rows_batch()
            return

        if parsed.path != TABLE_PATH:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        payload = self.read_json()
        if not isinstance(payload, dict):
            self.send_json({"error": "Expected JSON object"}, HTTPStatus.BAD_REQUEST)
            return

        with DATA_LOCK:
            rows = load_rows()
            row = self.prepare_row(payload)
            rows.append(row)
            save_rows(rows)
        self.send_json(row, HTTPStatus.CREATED)

    def create_rows_batch(self) -> None:
        payload = self.read_json()
        rows_payload = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows_payload, list):
            self.send_json({"error": "Expected JSON array or {rows: [...]}"}, HTTPStatus.BAD_REQUEST)
            return

        created = []
        with DATA_LOCK:
            rows = load_rows()
            for item in rows_payload:
                if not isinstance(item, dict):
                    continue
                row = self.prepare_row(item)
                rows.append(row)
                created.append(row)
            save_rows(rows)
        self.send_json({"data": created, "success": len(created), "failed": len(rows_payload) - len(created)}, HTTPStatus.CREATED)

    def prepare_row(self, payload: dict) -> dict:
        row = dict(payload)
        row.setdefault("id", uuid.uuid4().hex)
        row.setdefault("_serverCreatedAt", int(time.time() * 1000))
        return row

    def do_PUT(self) -> None:
        self.update_row(replace=True)

    def do_PATCH(self) -> None:
        self.update_row(replace=False)

    def update_row(self, replace: bool) -> None:
        row_id = self.table_row_id()
        if not row_id:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        payload = self.read_json()
        if not isinstance(payload, dict):
            self.send_json({"error": "Expected JSON object"}, HTTPStatus.BAD_REQUEST)
            return

        with DATA_LOCK:
            rows = load_rows()
            for index, row in enumerate(rows):
                if str(row.get("id")) == row_id:
                    updated = dict(payload) if replace else {**row, **payload}
                    updated["id"] = row_id
                    rows[index] = updated
                    save_rows(rows)
                    self.send_json(updated)
                    return
        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        by_model_prefix = f"{TABLE_PATH}/by-model/"
        if parsed.path.startswith(by_model_prefix):
            model_id = urllib.parse.unquote(parsed.path[len(by_model_prefix):])
            self.delete_rows_by_model(model_id)
            return

        row_id = self.table_row_id()
        if not row_id:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        with DATA_LOCK:
            rows = load_rows()
            remaining = [row for row in rows if str(row.get("id")) != row_id]
            if len(remaining) == len(rows):
                self.send_json({"deleted": False}, HTTPStatus.NOT_FOUND)
                return
            save_rows(remaining)
        self.send_json({"deleted": True, "id": row_id})

    def delete_rows_by_model(self, model_id: str) -> None:
        if not model_id:
            self.send_json({"error": "modelId is required"}, HTTPStatus.BAD_REQUEST)
            return
        with DATA_LOCK:
            rows = load_rows()
            remaining = [row for row in rows if str(row.get("modelId", "")) != model_id]
            deleted = len(rows) - len(remaining)
            save_rows(remaining)
        self.send_json({"deleted": deleted, "modelId": model_id})

    def handle_table_list(self, parsed: urllib.parse.ParseResult) -> None:
        query = urllib.parse.parse_qs(parsed.query)
        page = max(int(query.get("page", ["1"])[0] or 1), 1)
        limit = max(min(int(query.get("limit", ["100"])[0] or 100), 1000), 1)
        search = (query.get("search", [""])[0] or "").strip()
        model_id = (query.get("modelId", [""])[0] or "").strip()
        q = (query.get("q", [""])[0] or "").strip()

        with DATA_LOCK:
            rows = load_rows()
        filtered = filter_asset_rows(rows, model_id=model_id, q=q, search=search)
        start = (page - 1) * limit
        end = start + limit
        self.send_json(
            {
                "data": filtered[start:end],
                "total": len(filtered),
                "page": page,
                "limit": limit,
            }
        )

    def filter_rows(self, rows: list[dict], search: str) -> list[dict]:
        return filter_asset_rows(rows, search=search)

    def serve_static(self, request_path: str) -> None:
        safe_path = posixpath.normpath(urllib.parse.unquote(request_path)).lstrip("/")
        target = ROOT / (safe_path or "index.html")
        if target.is_dir():
            target = target / "index.html"
        try:
            target.relative_to(ROOT)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def table_row_id(self) -> str | None:
        parsed = urllib.parse.urlparse(self.path)
        prefix = TABLE_PATH + "/"
        if parsed.path.startswith(prefix):
            return urllib.parse.unquote(parsed.path[len(prefix) :])
        return None

    def send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8767")))
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), CashflowHandler)
    print(f"Cashflow system deployed at http://{args.host}:{args.port}/")
    print(f"Data file: {DATA_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
