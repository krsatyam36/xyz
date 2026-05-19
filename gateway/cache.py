from collections import OrderedDict
from typing import Optional
import hashlib
import time


class LRUCache:
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _make_key(self, model: str, messages: list, **kwargs) -> str:
        raw = f"{model}|{str(messages)}|{str(kwargs)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key]
        self.misses += 1
        return None

    def put(self, key: str, value: dict):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total * 100, 1) if total > 0 else 0,
        }


response_cache = LRUCache(max_size=500)
