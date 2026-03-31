"""
AI 클라이언트 래퍼 — 비용 인식 샘플링 + 적응형 조기 종료

비용 폭탄 방지 전략:
1. 적응형 샘플링: 초기 10회에서 점유율이 명확하면 조기 종료
2. 배치 캐싱: 동일 질문 결과 TTL 캐싱
3. Token Budget: max_tokens 질문 유형별 최소화
4. 비용 추적: 세션당 누적 토큰/비용 추정
"""

import time
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.logger import get_logger, CaptureError
from core.cache import get_cache
from core.citation import detect_citation, build_brand_variants, wilson_ci, CitationResult

logger = get_logger("ai_client")


# ─────────────────────────────────────────────
# 비용 추적기
# ─────────────────────────────────────────────
@dataclass
class CostTracker:
    """세션 내 API 비용 누적 추적 (USD 기준 추정)"""
    # GPT-4o-mini 가격 (2024 기준)
    GPT_PRICE_PER_1K_INPUT  = 0.00015
    GPT_PRICE_PER_1K_OUTPUT = 0.00060
    # Gemini Flash 가격
    GEM_PRICE_PER_1K_INPUT  = 0.000075
    GEM_PRICE_PER_1K_OUTPUT = 0.000300

    gpt_input_tokens: int  = 0
    gpt_output_tokens: int = 0
    gem_input_tokens: int  = 0
    gem_output_tokens: int = 0
    api_calls: int         = 0

    def add_gpt(self, input_t: int, output_t: int):
        self.gpt_input_tokens  += input_t
        self.gpt_output_tokens += output_t
        self.api_calls += 1

    def add_gemini(self, input_t: int, output_t: int):
        self.gem_input_tokens  += input_t
        self.gem_output_tokens += output_t
        self.api_calls += 1

    @property
    def estimated_usd(self) -> float:
        gpt = (self.gpt_input_tokens  / 1000 * self.GPT_PRICE_PER_1K_INPUT +
               self.gpt_output_tokens / 1000 * self.GPT_PRICE_PER_1K_OUTPUT)
        gem = (self.gem_input_tokens  / 1000 * self.GEM_PRICE_PER_1K_INPUT +
               self.gem_output_tokens / 1000 * self.GEM_PRICE_PER_1K_OUTPUT)
        return round(gpt + gem, 4)

    def summary(self) -> dict:
        return {
            "api_calls": self.api_calls,
            "estimated_usd": self.estimated_usd,
            "gpt_tokens": self.gpt_input_tokens + self.gpt_output_tokens,
            "gem_tokens": self.gem_input_tokens + self.gem_output_tokens,
        }


# ─────────────────────────────────────────────
# GPT 호출
# ─────────────────────────────────────────────
def call_gpt(client, prompt: str, system: str = "",
             model: str = "gpt-4o-mini",
             max_tokens: int = 300,
             temperature: float = 0.7,
             tracker: Optional[CostTracker] = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    with CaptureError("call_gpt", log_level="warning") as ctx:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        result = response.choices[0].message.content.strip()

        if tracker and hasattr(response, "usage"):
            tracker.add_gpt(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        return result

    raise RuntimeError(f"GPT 호출 실패: {ctx.error}")


# ─────────────────────────────────────────────
# Gemini 호출
# ─────────────────────────────────────────────
def call_gemini(model_obj, prompt: str,
                max_tokens: int = 300,
                temperature: float = 0.7,
                tracker: Optional[CostTracker] = None) -> str:
    import google.generativeai as genai

    with CaptureError("call_gemini", log_level="warning") as ctx:
        response = model_obj.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        text = response.text.strip()

        if tracker and hasattr(response, "usage_metadata"):
            um = response.usage_metadata
            tracker.add_gemini(
                getattr(um, "prompt_token_count", 0),
                getattr(um, "candidates_token_count", 0),
            )
        return text

    raise RuntimeError(f"Gemini 호출 실패: {ctx.error}")


# ─────────────────────────────────────────────
# 적응형 시뮬레이션 — 조기 종료 + 비용 최소화
# ─────────────────────────────────────────────
@dataclass
class SimResult:
    gpt_rate:    Optional[float]
    gemini_rate: Optional[float]
    avg_rate:    Optional[float]
    gpt_hits:    Optional[int]
    gemini_hits: Optional[int]
    n:           int
    gpt_ci:      tuple
    gemini_ci:   tuple
    gpt_samples:    list[str] = field(default_factory=list)
    gemini_samples: list[str] = field(default_factory=list)
    cost_summary:   dict = field(default_factory=dict)
    cache_hit:      bool = False

    def to_dict(self) -> dict:
        return {
            "gpt_rate":    self.gpt_rate,
            "gemini_rate": self.gemini_rate,
            "avg_rate":    self.avg_rate,
            "gpt_hits":    self.gpt_hits,
            "gemini_hits": self.gemini_hits,
            "n":           self.n,
            "gpt_ci":      self.gpt_ci,
            "gemini_ci":   self.gemini_ci,
            "gpt_samples": self.gpt_samples,
            "gemini_samples": self.gemini_samples,
        }


def _adaptive_batch(
    call_fn: Callable[[str], str],
    question: str,
    brand_variants: list[str],
    n: int,
    early_stop_threshold: float = 0.05,  # 95% 확신이면 조기 종료
) -> tuple[int, list[str], int]:
    """
    적응형 배치 실행.
    - 초기 min(10, n) 회 실행 후 점유율 확인
    - 0% 또는 100%에 가까우면 조기 종료 (비용 최소화)
    - 나머지: 전체 n회까지 실행
    반환: (hits, samples, actual_n)
    """
    hits = 0
    samples: list[str] = []
    actual_n = 0

    probe_n = min(10, n)
    probe_hits = 0

    # 초기 probe
    for _ in range(probe_n):
        with CaptureError("adaptive_probe", log_level="debug"):
            resp = call_fn(question)
            result: CitationResult = detect_citation(resp, brand_variants)
            if result.cited:
                probe_hits += 1
                if len(samples) < 3 and result.response_sample:
                    samples.append(result.response_sample)
        actual_n += 1

    probe_rate = probe_hits / probe_n if probe_n > 0 else 0

    # 조기 종료 판단
    lo, hi = wilson_ci(probe_hits, probe_n)
    if (hi < early_stop_threshold * 100) or (lo > (1 - early_stop_threshold) * 100):
        # 명확한 결과 → 나머지 실행 불필요
        logger.info(
            f"조기 종료: rate={probe_rate:.1%}, CI=[{lo:.1f},{hi:.1f}]% "
            f"({actual_n}/{n}회에서 확신)"
        )
        hits = probe_hits
        # 나머지는 probe 비율로 추정
        remaining_hits = round(probe_rate * (n - probe_n))
        hits_total = probe_hits + remaining_hits
        return hits_total, samples, n

    # 미확정 → 나머지 실행
    hits = probe_hits
    for _ in range(n - probe_n):
        with CaptureError("adaptive_full", log_level="debug"):
            resp = call_fn(question)
            result: CitationResult = detect_citation(resp, brand_variants)
            if result.cited:
                hits += 1
                if len(samples) < 3 and result.response_sample:
                    samples.append(result.response_sample)
        actual_n += 1

    return hits, samples, n


def run_simulation(
    client_gpt,
    client_gemini,
    question: str,
    target_url: str,
    model_gpt: str,
    n: int = 50,
    biz_info: dict = None,
    tracker: Optional[CostTracker] = None,
    use_cache: bool = True,
) -> SimResult:
    """
    단일 질문에 대해 GPT + Gemini 동시 시뮬레이션.
    결과는 TTL 캐시에 저장.
    """
    biz_info = biz_info or {}
    brand_variants = build_brand_variants(target_url, biz_info)
    cache = get_cache()

    # 캐시 체크
    if use_cache:
        cache_key = cache.make_key(
            "sim", target_url, question, model_gpt,
            n, ",".join(sorted(brand_variants))
        )
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT: simulation({question[:30]}...)")
            return SimResult(cache_hit=True, **cached)

    sim_prompt = f"질문: {question}\n\n답변:"

    def _gpt_call(q: str) -> str:
        return call_gpt(
            client_gpt, q,
            max_tokens=180,
            model=model_gpt,
            temperature=0.6,
            tracker=tracker,
        )

    def _gem_call(q: str) -> str:
        return call_gemini(
            client_gemini, q,
            max_tokens=180,
            temperature=0.6,
            tracker=tracker,
        )

    gpt_hits, gpt_samples, gpt_n = 0, [], 0
    gem_hits, gem_samples, gem_n = 0, [], 0
    gpt_ran = False
    gem_ran = False

    timeout = max(180, n * 4)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures = {}
        if client_gpt:
            futures["gpt"] = ex.submit(
                _adaptive_batch, _gpt_call, sim_prompt, brand_variants, n
            )
        if client_gemini:
            futures["gem"] = ex.submit(
                _adaptive_batch, _gem_call, sim_prompt, brand_variants, n
            )

        if "gpt" in futures:
            with CaptureError("gpt_future", log_level="warning") as ctx:
                gpt_hits, gpt_samples, gpt_n = futures["gpt"].result(timeout=timeout)
                gpt_ran = True
            if not ctx.ok:
                logger.warning(f"GPT simulation failed: {ctx.error}")

        if "gem" in futures:
            with CaptureError("gem_future", log_level="warning") as ctx:
                gem_hits, gem_samples, gem_n = futures["gem"].result(timeout=timeout)
                gem_ran = True
            if not ctx.ok:
                logger.warning(f"Gemini simulation failed: {ctx.error}")

    gpt_rate = round(gpt_hits / gpt_n * 100, 1) if gpt_ran and gpt_n > 0 else None
    gem_rate = round(gem_hits / gem_n * 100, 1) if gem_ran and gem_n > 0 else None
    valid    = [v for v in [gpt_rate, gem_rate] if v is not None]
    avg_rate = round(sum(valid) / len(valid), 1) if valid else None

    gpt_ci = wilson_ci(gpt_hits, gpt_n) if gpt_ran else (None, None)
    gem_ci = wilson_ci(gem_hits, gem_n) if gem_ran else (None, None)

    result = SimResult(
        gpt_rate=gpt_rate,
        gemini_rate=gem_rate,
        avg_rate=avg_rate,
        gpt_hits=gpt_hits if gpt_ran else None,
        gemini_hits=gem_hits if gem_ran else None,
        n=n,
        gpt_ci=gpt_ci,
        gemini_ci=gem_ci,
        gpt_samples=gpt_samples,
        gemini_samples=gem_samples,
        cost_summary=tracker.summary() if tracker else {},
    )

    if use_cache:
        cache.set(cache_key, result.to_dict(), namespace="sim")

    return result


def run_all_simulations(
    client_gpt,
    client_gemini,
    questions: list[str],
    target_url: str,
    model_gpt: str,
    n: int = 50,
    biz_info: dict = None,
    tracker: Optional[CostTracker] = None,
    use_cache: bool = True,
) -> list[SimResult]:
    """
    N개 질문 병렬 시뮬레이션.
    각 질문은 독립 스레드에서 실행.
    """
    results = [None] * len(questions)

    def _sim_one(idx: int, question: str):
        with CaptureError(f"sim_q{idx}", log_level="warning"):
            r = run_simulation(
                client_gpt, client_gemini, question, target_url,
                model_gpt, n=n, biz_info=biz_info,
                tracker=tracker, use_cache=use_cache,
            )
            results[idx] = r
            return

        # 에러 시 빈 결과
        results[idx] = SimResult(
            gpt_rate=None, gemini_rate=None, avg_rate=None,
            gpt_hits=None, gemini_hits=None,
            n=n, gpt_ci=(None, None), gemini_ci=(None, None),
        )

    max_workers = min(len(questions), 5)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_sim_one, i, q): i for i, q in enumerate(questions)}
        for fut in concurrent.futures.as_completed(futs):
            with CaptureError("sim_future_collect", log_level="warning"):
                fut.result(timeout=max(240, n * 5))

    return results
