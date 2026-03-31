"""
캐싱 레이어 — TTL 기반 인메모리 캐시
비용 폭탄 방지: 동일 URL/질문 결과를 TTL(기본 1시간) 동안 재사용
"""

import hashlib
import time
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl: float  # seconds

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class TTLCache:
    """
    Thread-safe TTL 캐시.
    - sim_results: 시뮬레이션 결과 (TTL 3600s)
    - biz_info: 비즈니스 분석 결과 (TTL 86400s — 하루)
    - competitors: 경쟁사 목록 (TTL 86400s)
    - crawl: 크롤링 결과 (TTL 3600s)
    """

    DEFAULT_TTL = {
        "sim": 3600,
        "biz": 86400,
        "competitors": 86400,
        "crawl": 3600,
        "strategy": 7200,
    }

    def __init__(self):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    # ── 키 생성 ──
    @staticmethod
    def make_key(namespace: str, *parts) -> str:
        raw = namespace + "|" + "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    # ── CRUD ──
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.is_expired:
                if entry:
                    del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, namespace: str = "sim") -> None:
        ttl = self.DEFAULT_TTL.get(namespace, 3600)
        with self._lock:
            self._store[key] = CacheEntry(value=value, created_at=time.time(), ttl=ttl)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear_expired(self) -> int:
        with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired]
            for k in expired:
                del self._store[k]
            return len(expired)

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total * 100, 1) if total else 0.0,
                "entries": len(self._store),
            }

    def to_serializable(self) -> dict:
        """Streamlit session_state 저장용 직렬화"""
        with self._lock:
            return {
                k: {"value": v.value, "created_at": v.created_at, "ttl": v.ttl}
                for k, v in self._store.items()
                if not v.is_expired
            }

    @classmethod
    def from_serializable(cls, data: dict) -> "TTLCache":
        cache = cls()
        for k, v in data.items():
            cache._store[k] = CacheEntry(
                value=v["value"],
                created_at=v["created_at"],
                ttl=v["ttl"],
            )
        return cache


# 전역 싱글톤
_global_cache = TTLCache()


def get_cache() -> TTLCache:
    return _global_cache
