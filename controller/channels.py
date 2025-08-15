# channels.py
import threading
from PySide6.QtCore import QObject, Signal

class ChannelStore(QObject):
    changed = Signal(str, object)  # emits (key, value)

    def __init__(self):
        super().__init__()
        self._data = {}
        self._lock = threading.RLock()

    def set(self, key: str, value):
        with self._lock:
            self._data[key] = value
        self.changed.emit(key, value)

    def update(self, mapping: dict):
        with self._lock:
            self._data.update(mapping)
            items = list(mapping.items())
        for k, v in items:
            self.changed.emit(k, v)

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._data)

channels = ChannelStore()
