import threading
from typing import Dict, Optional


class ActiveUserGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_owner: Optional[str] = None
        self._owner_running: Dict[str, int] = {}

    def can_start(self, owner: Optional[str], max_parallel: int) -> bool:
        if not owner:
            return False
        with self._lock:
            if self._active_owner is None:
                return True
            if self._active_owner != owner:
                return False
            return self._owner_running.get(owner, 0) < max_parallel

    def on_start(self, owner: Optional[str]) -> None:
        if not owner:
            return
        with self._lock:
            if self._active_owner is None:
                self._active_owner = owner
            self._owner_running[owner] = self._owner_running.get(owner, 0) + 1

    def on_finish(self, owner: Optional[str]) -> None:
        if not owner:
            return
        with self._lock:
            if owner not in self._owner_running:
                return
            self._owner_running[owner] -= 1
            if self._owner_running[owner] <= 0:
                del self._owner_running[owner]
                if self._active_owner == owner:
                    self._active_owner = None

    def active_owner(self) -> Optional[str]:
        with self._lock:
            return self._active_owner
