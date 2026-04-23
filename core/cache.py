"""
캐싱 레이어 — TTL 기반 인메모리 캐시 (v2.0 정리본)

핵심 클래스:
    TTLCache   — Thread-safe TTL 캐시 (get/set/stats)
    CacheEntry — 단일 캐시 항목 (value + created_at + ttl)

공개 함수:
    get_cache() → TTLCache  # 전역 싱글톤 반환

주의: get()은 Optional[Any] 단일값 반환.
      tuple unpacking (hit, val = cache.get(k)) 은 TypeError 발생.
      올바른 사용: val = cache.get(k); if val is not None: ...
"""

import hashlib
import time
import threading
from typing import Any, Optional


# ─────────────────────────────────────────────
# CacheEntry — 캐시 항목 (dataclass 불필요, 단순 클래스로 정의)
# ─────────────────────────────────────────────

class CacheEntry:
    __slots__ = ("value", "created_at", "ttl")

    def __init__(self, value: Any, created_at: float, ttl: float):
        self.value = value
        self.created_at = created_at
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


# ─────────────────────────────────────────────
# TTLCache — Thread-safe TTL 캐시
# ─────────────────────────────────────────────

class TTLCache:
    """
    Thread-safe TTL 캐시.

    네임스페이스별 TTL:
      sim         : 3600s  (시뮬레이션 결과)
      biz         : 86400s (비즈니스 분석)
      competitors : 86400s (경쟁사 목록)
      crawl       : 3600s  (크롤링 결과)
      strategy    : 7200s  (전략 분석)
    """

    DEFAULT_TTL = {
        "sim": 3600,
        "biz": 86400,
        "competitors": 86400,
        "crawl": 3600,
        "strategy": 7200,
    }

    def __init__(self):
        self._store = {}          # dict[str, CacheEntry]
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    # ── 키 생성 ──────────────────────────────────

    @staticmethod
    def make_key(namespace, *parts):
        raw = namespace + "|" + "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    # ── CRUD ──────────────────────────────────────

    def get(self, key):
        """
        캐시에서 값 반환.
        히트 → 값 반환 / 미스 또는 만료 → None 반환.

        올바른 사용:
            val = cache.get(key)
            if val is not None:
                use(val)
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.is_expired:
                if entry:
                    del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry.value

    def set(self, key, value, namespace="sim"):
        ttl = self.DEFAULT_TTL.get(namespace, 3600)
        with self._lock:
            self._store[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl,
            )

    def invalidate(self, key):
        with self._lock:
            self._store.pop(key, None)

    def clear_expired(self):
        with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired]
            for k in expired:
                del self._store[k]
            return len(expired)

    # ── 통계 ──────────────────────────────────────

    def stats(self):
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total * 100, 1) if total else 0.0,
                "entries": len(self._store),
            }

    # ── 직렬화 (Streamlit session_state 저장용) ───

    def to_serializable(self):
        with self._lock:
            return {
                k: {
                    "value": v.value,
                    "created_at": v.created_at,
                    "ttl": v.ttl,
                }
                for k, v in self._store.items()
                if not v.is_expired
            }

    @classmethod
    def from_serializable(cls, data):
        instance = cls()
        for k, v in data.items():
            try:
                instance._store[k] = CacheEntry(
                    value=v["value"],
                    created_at=v["created_at"],
                    ttl=v["ttl"],
                )
            except (KeyError, TypeError):
                pass  # 손상된 항목 무시
        return instance


# ─────────────────────────────────────────────
# 전역 싱글톤
# ─────────────────────────────────────────────

_global_cache = TTLCache()


def get_cache():
    # type: () -> TTLCache
    return _global_cache
