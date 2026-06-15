"""Shared web progress state."""

from __future__ import annotations

import threading
import time


class ProgressState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
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

    def update(self, step: str, percent: int, status: str = "running") -> None:
        with self._lock:
            self.step = step
            self.percent = percent
            self.status = status
            self.updated_at = time.time()

    def fail(self, error: str) -> None:
        with self._lock:
            self.step = "生成失败"
            self.percent = max(self.percent, 1)
            self.status = "failed"
            self.error = error
            self.updated_at = time.time()

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            now = time.time()
            return {
                "step": self.step,
                "percent": self.percent,
                "status": self.status,
                "error": self.error,
                "elapsed_seconds": int(now - self.started_at) if self.status != "idle" else 0,
                "updated_seconds_ago": int(now - self.updated_at),
            }


PROGRESS = ProgressState()

