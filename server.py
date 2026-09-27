import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brave_launcher import BraveLauncher
from cdp import CDPClient
from qwen_adapter import QwenAdapter

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["host"] = cfg.get("host", "127.0.0.1")
    cfg["port"] = int(cfg.get("port", 8787))
    return cfg


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.launcher = BraveLauncher(cfg)
        self.cdp = None
        self.adapter = QwenAdapter(self)
        self.lock = threading.Lock()

    def start_browser(self):
        if not self.cfg.get("auto_launch_brave", True):
            return
        self.launcher.ensure_running()

    def connect_qwen(self):
        with self.lock:
            if self.cdp and self.cdp.is_alive():
                return self.cdp
            targets = self.launcher.list_targets()
            qwen = None
            for t in targets:
                url = t.get("url", "")
                if "chat.qwen.ai" in url and t.get("webSocketDebuggerUrl"):
                    qwen = t
                    break
            if not qwen:
                return None
            self.cdp = CDPClient(qwen["webSocketDebuggerUrl"])
            self.cdp.connect()
            return self.cdp

    def status(self):
        targets = []
        try:
            targets = self.launcher.list_targets()
        except Exception:
            pass
        qwen = [
            {
                "title": t.get("title", ""),
                "url": t.get("url", ""),
                "type": t.get("type", ""),
            }
            for t in targets
            if "chat.qwen.ai" in t.get("url", "")
        ]
        return {
            "ok": True,
            "server": "qwen-claude-bridge",
            "browser": self.launcher.status(),
            "qwen_tabs": qwen,
            "anthropic_endpoint": "/v1/messages",
            "adapter_ready": self.adapter.ready,
        }


cfg = load_config()
app = App(cfg)


class Handler(BaseHTTPRequestHandler):
    server_version = "QwenClaudeBridge/0.1"

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, app.status())
            return

        if self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "qwen3.7-plus",
                            "object": "model",
                            "owned_by": "qwen-web-guest",
                        }
                    ],
                },
            )
            return

        self._send_json(404, {"error": {"type": "not_found", "message": "Not found"}})

    def do_POST(self):
        if self.path != "/v1/messages":
            self._send_json(404, {"error": {"type": "not_found", "message": "Not found"}})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            request = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(
                400,
                {"error": {"type": "invalid_request_error", "message": "Invalid JSON"}},
            )
            return

        result = app.adapter.handle_messages(request)
        if result.get("status") != 200:
            self._send_json(result["status"], result["body"])
            return

        self._send_json(200, result["body"])

    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)


def main():
    print("=" * 64)
    print(" Qwen Guest -> Claude Code Bridge")
    print("=" * 64)
    print(f" Local server: http://{cfg['host']}:{cfg['port']}")
    print(f" Health:       http://{cfg['host']}:{cfg['port']}/health")
    print()
    print("Starting dedicated Brave profile...")
    try:
        app.start_browser()
    except Exception as exc:
        print(f"[WARN] Could not launch Brave automatically: {exc}")

    print("Waiting briefly for DevTools...")
    time.sleep(1.5)

    try:
        app.connect_qwen()
        if app.cdp:
            print("[OK] Qwen tab detected.")
        else:
            print("[INFO] Qwen tab not detected yet.")
            print("       Open https://chat.qwen.ai in the dedicated Brave window.")
    except Exception as exc:
        print(f"[WARN] CDP connection not ready: {exc}")

    httpd = ThreadingHTTPServer((cfg["host"], cfg["port"]), Handler)
    print()
    print("Server running. Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        httpd.server_close()
        if app.cdp:
            app.cdp.close()


if __name__ == "__main__":
    main()
