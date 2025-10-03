from cachetools import TTLCache
from typing import Any, Dict, Optional, Tuple
import time


class QueryCache:
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.cache = TTLCache(maxsize=max_size, ttl=ttl)
        self.metrics = {"hits": 0, "misses": 0}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        value = self.cache.get(key)
        if value is None:
            self.metrics["misses"] += 1
        else:
            self.metrics["hits"] += 1
        return value

    def set(self, key: str, value: Dict[str, Any]):
        self.cache[key] = value

    def stats(self) -> Dict[str, int]:
        return dict(self.metrics)
