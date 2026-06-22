"""Shared web progress state."""

from __future__ import annotations

import threading
import time
import subprocess
import os
import signal
from typing import Dict


class ProgressState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[int, subprocess.Popen[object]] = {}
        self.reset("待命", 0, "idle")

    def reset(self, step: str, percent: int, status: str) -> None:
        with self._lock:
            now = time.time()
            self.started_at = now
            self.updated_at = now
            self.step = step
            self.percent = percent
            self.status = status
            self.error = ""
            self.cancel_requested = False

    def update(self, step: str, percent: int, status: str = "running") -> None:
        with self._lock:
            self.step = step
            self.percent = percent
            self.status = status
            if status in {"running", "completed"}:
                self.error = ""
            if status == "completed":
                self.cancel_requested = False
            self.updated_at = time.time()

    def fail(self, error: str) -> None:
        with self._lock:
            if getattr(self, "cancel_requested", False):
                self.step = "任务已停止"
                self.percent = max(self.percent, 1)
                self.status = "cancelled"
                self.error = "任务已停止"
                self.updated_at = time.time()
                return
            self.step = "生成失败"
            self.percent = max(self.percent, 1)
            self.status = "failed"
            self.error = error
            self.updated_at = time.time()

    def cancel(self) -> None:
        with self._lock:
            self.cancel_requested = True
            self.step = "正在停止当前任务"
            self.percent = max(self.percent, 1)
            self.status = "cancelled"
            self.error = "任务已停止"
            self.updated_at = time.time()
            processes = list(self._processes.values())
        for process in processes:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except Exception:
                    process.terminate()

    def is_cancelled(self) -> bool:
        with self._lock:
            return bool(getattr(self, "cancel_requested", False))

    def register_process(self, process: subprocess.Popen[object]) -> None:
        with self._lock:
            self._processes[process.pid] = process

    def unregister_process(self, process: subprocess.Popen[object]) -> None:
        with self._lock:
            self._processes.pop(process.pid, None)

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            now = time.time()
            return {
                "step": self.step,
                "percent": self.percent,
                "status": self.status,
                "error": self.error,
                "cancel_requested": bool(getattr(self, "cancel_requested", False)),
                "active_process_count": len(self._processes),
                "elapsed_seconds": int((self.updated_at if self.status in {"completed", "failed", "cancelled"} else now) - self.started_at) if self.status != "idle" else 0,
                "updated_seconds_ago": int(now - self.updated_at),
            }


PROGRESS = ProgressState()
