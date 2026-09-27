import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


class BraveLauncher:
    def __init__(self, cfg):
        self.cfg = cfg
        root = Path(__file__).resolve().parent
        raw_profile = Path(cfg.get("brave_profile_dir", "./brave-profile"))
        self.profile_dir = raw_profile if raw_profile.is_absolute() else root / raw_profile
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.debug_port = 9222
        self.proc = None

    def find_executable(self):
        configured = self.cfg.get("brave_path", "").strip()
        candidates = []
        if configured:
            candidates.append(Path(configured))

        local = os.environ.get("LOCALAPPDATA", "")
        program = os.environ.get("PROGRAMFILES", "")
        program_x86 = os.environ.get("PROGRAMFILES(X86)", "")

        candidates += [
            Path(local) / "BraveSoftware/Brave-Browser/Application/brave.exe",
            Path(program) / "BraveSoftware/Brave-Browser/Application/brave.exe",
            Path(program_x86) / "BraveSoftware/Brave-Browser/Application/brave.exe",
        ]

        for p in candidates:
            if p.exists():
                return str(p)

        raise FileNotFoundError(
            "Brave executable not found. Put its full path in config.json "
            'under "brave_path".'
        )

    def _json_url(self, path):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self.debug_port}{path}", timeout=1.5
        ) as r:
            return json.loads(r.read().decode("utf-8"))

    def list_targets(self):
        return self._json_url("/json/list")

    def debugger_ready(self):
        try:
            self._json_url("/json/version")
            return True
        except Exception:
            return False

    def ensure_running(self):
        if self.debugger_ready():
            return

        exe = self.find_executable()
        args = [
            exe,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "https://chat.qwen.ai",
        ]

        print("[INFO] Launching dedicated Brave profile:")
        print(f"       {self.profile_dir}")
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.time() + 15
        while time.time() < deadline:
            if self.debugger_ready():
                return
            time.sleep(0.25)

        raise RuntimeError(
            f"Brave started, but DevTools port {self.debug_port} did not become ready."
        )

    def status(self):
        return {
            "debug_port": self.debug_port,
            "running": self.debugger_ready(),
            "profile_dir": str(self.profile_dir),
        }
