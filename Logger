"""
구조화 로거 — 디버깅 가능한 에러 추적
모든 except Exception: pass 대체
"""

import logging
import traceback
import time
from dataclasses import dataclass, field
from typing import Optional
from functools import wraps


# ── 로그 포맷 설정 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"aca.{name}")


# ── 에러 컨텍스트 ──
@dataclass
class ErrorContext:
    operation: str
    error: Exception
    traceback_str: str
    timestamp: float = field(default_factory=time.time)
    extra: dict = field(default_factory=dict)

    def __str__(self):
        return f"[{self.operation}] {type(self.error).__name__}: {self.error}"

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "error_type": type(self.error).__name__,
            "error_msg": str(self.error),
            "traceback": self.traceback_str,
            "timestamp": self.timestamp,
            **self.extra,
        }


# ── safe_call 데코레이터 ──
def safe_call(operation: str, default=None, log_level="warning"):
    """
    함수 실행 실패 시 default 반환 + 구조화 로그 출력.
    except Exception: pass 대신 이걸 사용.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            logger = get_logger(fn.__module__ or "unknown")
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                tb = traceback.format_exc()
                ctx = ErrorContext(
                    operation=operation,
                    error=e,
                    traceback_str=tb,
                )
                log_fn = getattr(logger, log_level, logger.warning)
                log_fn(str(ctx))
                logger.debug(f"Traceback:\n{tb}")
                return default
        return wrapper
    return decorator


# ── 컨텍스트 매니저 ──
class CaptureError:
    """
    with CaptureError("operation") as ctx:
        ...위험한 코드...
    if ctx.error:
        handle(ctx.error)
    """
    def __init__(self, operation: str, reraise=False, log_level="warning"):
        self.operation = operation
        self.reraise = reraise
        self.log_level = log_level
        self.error: Optional[Exception] = None
        self.error_ctx: Optional[ErrorContext] = None
        self._logger = get_logger("capture")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.error = exc_val
            self.error_ctx = ErrorContext(
                operation=self.operation,
                error=exc_val,
                traceback_str=traceback.format_exc(),
            )
            log_fn = getattr(self._logger, self.log_level, self._logger.warning)
            log_fn(str(self.error_ctx))
            return not self.reraise  # True → 예외 억제
        return False

    @property
    def ok(self) -> bool:
        return self.error is None
