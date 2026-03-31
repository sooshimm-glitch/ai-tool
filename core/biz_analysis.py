"""
비즈니스 분석 & 경쟁사 도출
개선 포인트:
- 크롤링 → AI 분석 → 검색 검증 → AI 재확인 파이프라인
- 업종 추출 정확도 향상 (포괄적 업종명 retry)
- 경쟁사 도출: 검색 결과 + AI 추론 + 도메인 존재 검증
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional

from core.logger import get_logger, CaptureError
from core.cache import get_cache
from core.crawler import crawl, crawl_search, CrawlResult
from core.ai_client import call_gpt, call_gemini

logger = get_logger("biz_analysis")

_BAD_INDUSTRIES = {
    "디지털 서비스", "it 서비스", "온라인 서비스",
    "인터넷 서비스", "웹 서비스", "소프트웨어",
    "technology", "tech company", "internet company",
}


# ─────────────────────────────────────────────
# 데이터 스키마
# ─────────────────────────────────────────────
@dataclass
class BusinessInfo:
    brand_name: str
    industry: str
    industry_category: str
    core_product: str
    target_audience: str
    key_services: list[str] = field(default_factory=list)
    confidence: str = "medium"   # low / medium / high
    crawl_tier: int = 0

    def is_vague_industry(self) -> bool:
        return any(bad in self.industry.lower() for bad in _BAD_INDUSTRIES)

    def to_dict(self) -> dict:
        return {
            "brand_name":        self.brand_name,
            "industry":          self.industry,
            "industry_category": self.industry_category,
            "core_product":      self.core_product,
            "target_audience":   self.target_audience,
            "key_services":      self.key_services,
            "confidence":        self.confidence,
            "crawl_tier":        self.crawl_tier,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BusinessInfo":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Competitor:
    rank: int
    brand_name: str
    domain: str
    reason: str
    market_position: str
    verified: bool = False
    evidence: str = ""


# ─────────────────────────────────────────────
# 업종 분석 프롬프트
# ─────────────────────────────────────────────
_BIZ_SYSTEM = (
    "당신은 비즈니스 인텔리전스 전문가입니다. "
    "모든 분석은 제공된 데이터에 근거하여 구체적으로 수행합니다."
)

def _build_biz_prompt(domain: str, crawl_result: CrawlResult, search_ctx: str) -> str:
    return f"""아래 데이터를 분석하여 해당 웹사이트의 업종과 서비스를 정확히 파악하세요.

[도메인]
{domain}

[크롤링 데이터 (Tier {crawl_result.tier_used})]
{crawl_result.summary(max_len=2500)}

[웹 검색 보완 데이터]
{search_ctx[:2000] if search_ctx else "(없음)"}

[분석 지침]
- 업종은 반드시 구체적인 카테고리로 작성
  ✅ 좋은 예: "퍼포먼스 마케팅 광고대행사", "온라인 패션 쇼핑몰", "B2B SaaS HR솔루션"
  ❌ 나쁜 예: "IT 서비스", "디지털 서비스", "온라인 서비스"
- brand_name은 도메인이 아닌 실제 회사명/브랜드명
- 데이터가 부족하면 도메인과 검색 맥락으로 추론
- 광고/마케팅 키워드(대행사, 퍼포먼스, IMC, GFA, 매체 등)가 있으면 광고대행사 계열 분류
- confidence: 크롤 성공+데이터 풍부=high, 크롤 성공+데이터 보통=medium, 크롤 실패=low

다른 설명 없이 JSON만 출력:
{{
  "brand_name": "실제 브랜드명",
  "industry": "구체적 업종",
  "industry_category": "광고/마케팅 | 이커머스 | SaaS | 금융 | 교육 | 의료 | 부동산 | 제조 | 물류 | 미디어 | 게임 | 기타 중 택1",
  "core_product": "핵심 서비스/상품 한 문장",
  "target_audience": "주요 타겟 고객층",
  "key_services": ["서비스1", "서비스2", "서비스3"],
  "confidence": "high | medium | low 중 택1"
}}"""


# ─────────────────────────────────────────────
# 비즈니스 분석 (메인)
# ─────────────────────────────────────────────
def analyze_business(
    client_gpt, client_gemini,
    url: str,
    model_gpt: str,
    confirmed_industry: str = "",
    use_cache: bool = True,
) -> BusinessInfo:
    """
    Pipeline:
    1. 3-tier 크롤링
    2. 업종 검색 보완 (Jina Search)
    3. AI 업종 분석
    4. 업종 모호 → AI retry
    5. 사용자 확정 업종 최우선 반영
    """
    from urllib.parse import urlparse
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = url

    cache = get_cache()
    if use_cache:
        key = cache.make_key("biz", url, confirmed_industry)
        cached = cache.get(key)
        if cached:
            logger.info(f"Cache HIT: biz_analysis({domain})")
            return BusinessInfo.from_dict(cached)

    # Step 1: 크롤링
    crawl_result = crawl(url, use_cache=use_cache)

    # Step 2: 검색 보완
    stem = domain.split(".")[0]
    search_ctx = ""
    if not crawl_result.ok or len(crawl_result.body_text) < 200:
        search_ctx = crawl_search(f"{stem} 서비스 업종 소개")
        if not search_ctx:
            search_ctx = crawl_search(f"{stem} company overview service")

    # Step 3: AI 분석
    prompt = _build_biz_prompt(domain, crawl_result, search_ctx)
    result_str = ""

    with CaptureError("biz_ai_call", log_level="warning") as ctx:
        if client_gpt:
            result_str = call_gpt(
                client_gpt, prompt,
                system=_BIZ_SYSTEM,
                max_tokens=500,
                model=model_gpt,
                temperature=0.15,
            )
        elif client_gemini:
            result_str = call_gemini(
                client_gemini, prompt,
                max_tokens=500,
                temperature=0.15,
            )

    biz_dict = {}
    with CaptureError("biz_json_parse", log_level="warning"):
        m = re.search(r'\{.*\}', result_str, re.DOTALL)
        if m:
            biz_dict = json.loads(m.group())

    # Step 4: 업종 모호 → retry
    if biz_dict:
        industry = biz_dict.get("industry", "")
        if any(bad in industry.lower() for bad in _BAD_INDUSTRIES):
            retry_prompt = f"""도메인 "{domain}"의 업종을 아래 정보로 정확히 분류하세요.

크롤링 데이터: {crawl_result.summary(max_len=1000)}
검색 데이터: {search_ctx[:1000] if search_ctx else '없음'}

구체적인 업종명으로만 JSON 출력 (예: {{"industry": "퍼포먼스 마케팅 광고대행사"}}):"""

            with CaptureError("biz_industry_retry", log_level="warning"):
                r2 = (
                    call_gpt(client_gpt, retry_prompt, max_tokens=80, model=model_gpt, temperature=0.1)
                    if client_gpt else
                    call_gemini(client_gemini, retry_prompt, max_tokens=80, temperature=0.1)
                )
                m2 = re.search(r'\{.*\}', r2, re.DOTALL)
                if m2:
                    new_industry = json.loads(m2.group()).get("industry", "")
                    if new_industry and not any(bad in new_industry.lower() for bad in _BAD_INDUSTRIES):
                        biz_dict["industry"] = new_industry

    if not biz_dict:
        biz_dict = {
            "brand_name":        stem.upper(),
            "industry":          f"{stem} 관련 서비스",
            "industry_category": "기타",
            "core_product":      f"{domain} 서비스",
            "target_audience":   "잠재 고객",
            "key_services":      [],
            "confidence":        "low",
        }

    biz_dict["crawl_tier"] = crawl_result.tier_used

    # Step 5: 사용자 확정 업종 최우선
    if confirmed_industry.strip():
        biz_dict["industry"] = confirmed_industry.strip()
        biz_dict["confidence"] = "high"

    biz = BusinessInfo.from_dict(biz_dict)

    if use_cache:
        key = cache.make_key("biz", url, confirmed_industry)
        cache.set(key, biz.to_dict(), namespace="biz")

    return biz


# ─────────────────────────────────────────────
# 경쟁사 도출
# ─────────────────────────────────────────────
_COMPETITOR_SYSTEM = "당신은 디지털 마케팅 시장 분석 전문가입니다."

def discover_competitors(
    client_gpt, client_gemini,
    biz_info: BusinessInfo,
    target_url: str,
    market_scope: str,
    model_gpt: str,
    n_competitors: int = 5,
    use_cache: bool = True,
) -> list[Competitor]:
    """
    검색 데이터 기반 경쟁사 도출 + 도메인 검증.
    Pipeline:
    1. Jina Search로 실제 검색 결과 수집 (2~3개 쿼리)
    2. AI로 경쟁사 도출 (검색 근거 활용)
    3. domain_valid + is_direct_competitor 필터
    """
    from urllib.parse import urlparse
    try:
        p = urlparse(target_url if target_url.startswith("http") else "https://" + target_url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = target_url

    cache = get_cache()
    if use_cache:
        key = cache.make_key(
            "competitors", target_url, biz_info.industry, market_scope, n_competitors
        )
        cached = cache.get(key)
        if cached:
            logger.info(f"Cache HIT: competitors({domain})")
            return [Competitor(**c) for c in cached]

    scope_kw = "한국 국내" if "국내" in market_scope else "글로벌"
    scope_inst = (
        "반드시 대한민국에서 서비스 중인 국내 기업만 포함하세요. 해외 기업은 제외합니다."
        if "국내" in market_scope
        else "전 세계 글로벌 시장에서 활동하는 기업을 포함하세요."
    )

    # 검색 데이터 수집
    search_data = []
    for q in [
        f"{biz_info.industry} 경쟁사 {scope_kw}",
        f"{biz_info.brand_name} 대안 {biz_info.industry}",
        f"{biz_info.industry} 주요 기업 비교 {scope_kw}",
    ]:
        ctx = crawl_search(q, use_cache=use_cache)
        if ctx:
            search_data.append(f"[{q}]\n{ctx[:2000]}")

    search_section = (
        "[실제 검색 데이터 — 최우선 근거]\n" + "\n\n".join(search_data[:2])
        if search_data
        else "[검색 데이터: 없음 — AI 자체 지식으로 판단]"
    )

    prompt = f"""당신은 {biz_info.industry} 분야의 시장 분석 전문가입니다.

[분석 대상]
- 브랜드: {biz_info.brand_name}
- 도메인: {domain}
- 업종: {biz_info.industry} ({biz_info.industry_category})
- 핵심 서비스: {biz_info.core_product}
- 타겟: {biz_info.target_audience}

{search_section}

[경쟁사 선정 기준]
1. 위 검색 데이터에 등장하는 브랜드 최우선
2. {biz_info.industry}와 동일 카테고리에서 직접 경쟁
3. {biz_info.brand_name} 고객이 이탈 시 선택할 가능성 높은 대안
4. {scope_inst}
5. {domain} 자체는 절대 포함 금지

[검증 조건 — 반드시 준수]
- domain_valid: 실제 운영 중인 도메인만 (가상 도메인 제외)
- is_direct_competitor: 동일 고객을 두고 직접 경쟁하는 서비스만

두 조건 모두 true인 항목 {n_competitors}개만 JSON 배열로 출력:
[
  {{
    "rank": 1,
    "brand_name": "브랜드명",
    "domain": "실제도메인.com",
    "reason": "경쟁 이유 20자 이내",
    "market_position": "업계 1위 | 신흥 강자 | 틈새 전문 중 택1",
    "domain_valid": true,
    "is_direct_competitor": true,
    "evidence": "검색 데이터 근거 또는 AI 판단"
  }}
]"""

    result_str = ""
    with CaptureError("competitor_ai", log_level="warning"):
        if client_gpt:
            result_str = call_gpt(
                client_gpt, prompt,
                system=_COMPETITOR_SYSTEM,
                max_tokens=1200,
                model=model_gpt,
                temperature=0.2,
            )
        elif client_gemini:
            result_str = call_gemini(
                client_gemini, prompt,
                max_tokens=1200,
                temperature=0.2,
            )

    competitors: list[Competitor] = []
    with CaptureError("competitor_parse", log_level="warning"):
        m = re.search(r'\[.*\]', result_str, re.DOTALL)
        if m:
            raw = json.loads(m.group())
            for c in raw:
                if (c.get("domain_valid", True)
                        and c.get("is_direct_competitor", True)
                        and c.get("domain", "").strip()
                        and "competitor" not in c.get("domain", "").lower()):
                    competitors.append(Competitor(
                        rank=c.get("rank", len(competitors) + 1),
                        brand_name=c.get("brand_name", c.get("domain", "")),
                        domain=c.get("domain", ""),
                        reason=c.get("reason", ""),
                        market_position=c.get("market_position", ""),
                        verified=True,
                        evidence=c.get("evidence", ""),
                    ))

    # 폴백
    if not competitors:
        logger.warning(f"경쟁사 도출 실패, 폴백 사용: {domain}")
        competitors = [
            Competitor(rank=i+1, brand_name=f"경쟁사 {i+1}",
                       domain=f"competitor{i+1}.com", reason="동종 업계",
                       market_position="시장 참여자")
            for i in range(n_competitors)
        ]

    result = competitors[:n_competitors]

    if use_cache:
        key = cache.make_key(
            "competitors", target_url, biz_info.industry, market_scope, n_competitors
        )
        cache.set(key, [c.__dict__ for c in result], namespace="competitors")

    return result


# ─────────────────────────────────────────────
# 타겟 질문 생성
# ─────────────────────────────────────────────
_QUESTION_SYSTEM = (
    "당신은 GEO(Generative Engine Optimization) 전문가이자 디지털 마케팅 전략가입니다. "
    "완성된 질문만 출력합니다."
)

_CATEGORY_HINTS = {
    "광고/마케팅": (
        "광고주(중소기업 대표, 마케터)가 대행사를 선택할 때 묻는 질문 — "
        "ROAS, CPA, 매체비, 대행수수료, 업종 레퍼런스 위주"
    ),
    "이커머스": "구매자의 배송·가격·신뢰도, 판매자의 입점·수수료 관련 질문",
    "SaaS": "도입 전 데모·연동·보안·가격 플랜, 기존 솔루션 전환 비용 관련 질문",
    "금융": "금리·한도·수수료·안전성, 타 금융사 대비 혜택 관련 질문",
    "교육": "커리큘럼·강사·합격률·환불정책, 취업 연계 관련 질문",
    "의료": "진료 과목·비용·예약, 전문성 관련 질문",
    "게임": "게임성·과금정책·PC/모바일 지원, 경쟁 타이틀 대비 질문",
}


def generate_target_questions(
    client_gpt, client_gemini,
    url: str,
    engine: str,
    model_gpt: str,
    biz_info: Optional[BusinessInfo] = None,
    use_cache: bool = True,
) -> list[str]:
    """
    비즈니스 정보 기반 고품질 타겟 질문 5개 생성.
    """
    from urllib.parse import urlparse
    try:
        p = urlparse(url if url.startswith("http") else "https://" + url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = url

    if biz_info is None:
        biz_info = BusinessInfo(
            brand_name=domain.split(".")[0].upper(),
            industry="서비스",
            industry_category="기타",
            core_product="서비스",
            target_audience="잠재 고객",
        )

    cache = get_cache()
    if use_cache:
        key = cache.make_key("questions", url, biz_info.industry, engine)
        cached = cache.get(key)
        if cached:
            logger.info(f"Cache HIT: questions({domain})")
            return cached

    category_hint = _CATEGORY_HINTS.get(
        biz_info.industry_category,
        f"{biz_info.industry} 분야에서 {biz_info.target_audience}가 실제로 고민하는 핵심 질문"
    )
    services_str = ", ".join(biz_info.key_services) if biz_info.key_services else biz_info.core_product

    prompt = f"""당신은 {biz_info.industry} 분야 10년 경력 마케팅 전략가이자 GEO 전문가입니다.

[분석 대상]
- 브랜드명: {biz_info.brand_name}  ← 질문에 반드시 이 이름을 자연스럽게 포함
- 업종: {biz_info.industry} ({biz_info.industry_category})
- 핵심 서비스: {services_str}
- 주요 타겟: {biz_info.target_audience}
- 도메인(참고용, 질문에 사용 금지): {domain}

[질문 방향]
{category_hint}

[생성 규칙]
1. {biz_info.target_audience}가 "{biz_info.brand_name}"을 도입/계약/구매 결정할 때 AI에 입력하는 현실적 질문
2. 구매 결정 5단계(인지→비교→신뢰→가격→전환)를 각각 다룰 것
3. {biz_info.industry} 업계 전문 용어·지표·관행 적극 활용
4. "~는 무엇인가요?", "~를 소개해주세요" 같은 기초 탐색형 질문 금지
5. 구체적 수치·비교·상황이 포함된 깊이 있는 질문

[예시 (이 톤앤매너 준수)]
✅ "{biz_info.brand_name}의 퍼포먼스 마케팅 집행 시 타 대행사 대비 평균 ROAS 달성 수치는?"
✅ "{biz_info.brand_name}를 도입한 기업이 6개월 내 달성한 전환율 개선치와 ROI는?"
❌ "{biz_info.brand_name}는 무엇을 하는 회사인가요?"

번호·라벨 없이 질문 5개만 출력. 한 줄에 하나. 물음표(?)로 종결. 도메인 주소 금지."""

    result_str = ""
    with CaptureError("question_gen", log_level="warning") as ctx:
        if engine == "GPT" and client_gpt:
            result_str = call_gpt(
                client_gpt, prompt,
                system=_QUESTION_SYSTEM,
                max_tokens=600,
                model=model_gpt,
                temperature=0.85,
            )
        elif client_gemini:
            result_str = call_gemini(
                client_gemini, prompt,
                max_tokens=600,
                temperature=0.85,
            )
        elif client_gpt:
            result_str = call_gpt(
                client_gpt, prompt,
                system=_QUESTION_SYSTEM,
                max_tokens=600,
                model=model_gpt,
                temperature=0.85,
            )

    if not result_str and not ctx.ok:
        raise RuntimeError(f"질문 생성 실패: {ctx.error}")

    # 파싱
    lines = [ln.strip() for ln in result_str.split("\n") if ln.strip()]
    questions = []
    for ln in lines:
        clean = re.sub(r'^[\d]+[.)]\s*', '', ln)
        clean = re.sub(r'^[-•*]\s*', '', clean)
        clean = re.sub(r'^\[.*?\]\s*', '', clean)
        clean = re.sub(r'^\*\*.*?\*\*\s*', '', clean).strip()
        if len(clean) > 10:
            if not clean.endswith("?"):
                clean += "?"
            questions.append(clean)

    questions = questions[:5]

    # 폴백
    if len(questions) < 3:
        is_ad = "광고" in biz_info.industry or "마케팅" in biz_info.industry
        if is_ad:
            questions = [
                f"{biz_info.brand_name}의 업종별 광고 ROAS가 타 대행사 대비 어느 수준인가요?",
                f"{biz_info.target_audience}가 {biz_info.brand_name}에 광고를 맡기기 전 확인할 계약 조건은?",
                f"{biz_info.brand_name}의 주요 집행 매체와 공식 파트너십 현황은?",
                f"{biz_info.brand_name} 광고 집행 시 직접 운영 대비 대행수수료 구조는?",
                f"{biz_info.brand_name}의 실제 광고주 성과 사례와 평균 CPA 수준은?",
            ]
        else:
            questions = [
                f"{biz_info.brand_name}이 {biz_info.industry} 시장에서 경쟁사 대비 실제로 다른 점은?",
                f"{biz_info.target_audience}가 {biz_info.brand_name} 선택 후 실제 얻은 성과는?",
                f"{biz_info.brand_name}의 계약·이용 조건과 비용 구조가 동종 업계 대비 어떤 수준인가요?",
                f"{biz_info.brand_name}에 대한 실제 사용자 평가와 주요 불만 사항은?",
                f"{biz_info.industry}에서 {biz_info.brand_name}과 직접 비교되는 대안 서비스는?",
            ]

    result = questions[:5]

    if use_cache:
        key = cache.make_key("questions", url, biz_info.industry, engine)
        cache.set(key, result, namespace="biz")

    return result


# ─────────────────────────────────────────────
# 전략 분석
# ─────────────────────────────────────────────
def run_strategy_analysis(
    client_gpt, client_gemini,
    question: str,
    target_url: str,
    model_gpt: str,
    biz_info: Optional[BusinessInfo] = None,
    market_scope: str = "글로벌",
    use_cache: bool = True,
) -> dict:
    from urllib.parse import urlparse
    try:
        p = urlparse(target_url if target_url.startswith("http") else "https://" + target_url)
        domain = p.netloc.replace("www.", "")
    except Exception:
        domain = target_url

    cache = get_cache()
    if use_cache:
        key = cache.make_key("strategy", target_url, question[:50], market_scope)
        cached = cache.get(key)
        if cached:
            logger.info(f"Cache HIT: strategy({question[:30]}...)")
            return cached

    biz = biz_info or BusinessInfo(
        brand_name=domain, industry="서비스", industry_category="기타",
        core_product="서비스", target_audience="고객",
    )
    scope_inst = (
        "반드시 대한민국에서 서비스하는 국내 기업만 포함하세요."
        if "국내" in market_scope
        else "국내외 글로벌 기업을 모두 포함하세요."
    )
    _system = (
        "당신은 디지털 마케팅 전략 컨설턴트입니다. "
        "모든 답변은 완성된 문장으로, 중간에 끊기지 않게 서술하세요."
    )

    # ── 경쟁사 현황 ──
    comp_prompt = f"""질문: "{question}"

이 질문에 답변할 때 AI(ChatGPT, Gemini 등)가 자주 인용할 상위 10개 웹사이트/브랜드를 인용 가능성 순으로 나열하세요.

조건:
- 분석 대상: {biz.brand_name} (업종: {biz.industry})
- {scope_inst}
- {domain}도 적절한 순위에 포함
- 각 항목에 인용 이유와 경쟁 포지션 명시

JSON 배열만 출력:
[{{"rank":1,"domain":"example.com","brand_name":"브랜드명","reason":"이유 20자","position":"업계1위|신흥강자|틈새전문 중 택1"}}]"""

    comp_str = ""
    with CaptureError("strategy_comp", log_level="warning"):
        if client_gpt:
            comp_str = call_gpt(client_gpt, comp_prompt, system=_system,
                                max_tokens=1200, model=model_gpt, temperature=0.3)
        elif client_gemini:
            comp_str = call_gemini(client_gemini, comp_prompt, max_tokens=1200, temperature=0.3)

    competitors = []
    with CaptureError("strategy_comp_parse", log_level="warning"):
        m = re.search(r'\[.*\]', comp_str, re.DOTALL)
        if m:
            competitors = json.loads(m.group())

    if not competitors:
        competitors = [{"rank": i+1, "domain": f"c{i+1}.com", "brand_name": f"경쟁사{i+1}",
                        "reason": "관련 전문 사이트", "position": "시장 참여자"} for i in range(5)]

    # ── 진단 + 키워드 + GEO 병렬 ──
    def _diagnosis():
        p = f"""{domain} ({biz.brand_name}, {biz.industry})이 "{question}"에서 AI 인용 점유율이 낮은 원인 3가지.
경쟁사 대비 구체적 문제점. 각 항목 50자 이내. 번호 없이 한 줄씩:"""
        with CaptureError("strategy_diag", log_level="warning") as c:
            r = (call_gpt(client_gpt, p, system=_system, max_tokens=600, model=model_gpt, temperature=0.4)
                 if client_gpt else
                 call_gemini(client_gemini, p, max_tokens=600, temperature=0.4))
            return [d.strip().lstrip("•-*") for d in r.split("\n") if d.strip()][:3]
        return []

    def _keywords():
        p = f"""{biz.brand_name} ({biz.industry}) 사이트에서 AI 인용 확률이 높은 블루오션 키워드 5개.
경쟁 적고 전문성 높은 틈새 키워드. {scope_inst} 키워드만, 한 줄에 하나:"""
        with CaptureError("strategy_kw", log_level="warning") as c:
            r = (call_gemini(client_gemini, p, max_tokens=600, temperature=0.7)
                 if client_gemini else
                 call_gpt(client_gpt, p, system=_system, max_tokens=600, model=model_gpt, temperature=0.7))
            return [k.strip().lstrip("•-*1234567890. ") for k in r.split("\n") if k.strip()][:5]
        return []

    def _geo():
        p = f"""{domain} ({biz.brand_name})이 "{question}"에서 AI에 더 잘 인용되도록 홈페이지 개선 방안 3가지.
구체적 문구 수정 또는 구조 변경 제안 포함. 각 항목 2줄 이내. 번호 포함:"""
        with CaptureError("strategy_geo", log_level="warning") as c:
            r = (call_gpt(client_gpt, p, system=_system, max_tokens=1000, model=model_gpt, temperature=0.5)
                 if client_gpt else
                 call_gemini(client_gemini, p, max_tokens=1000, temperature=0.5))
            return [g.strip() for g in re.split(r'\n(?=\d+\.)', r) if g.strip()][:3]
        return []

    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        f_diag = ex.submit(_diagnosis)
        f_kw   = ex.submit(_keywords)
        f_geo  = ex.submit(_geo)

        diagnoses  = f_diag.result(timeout=60) or ["데이터 부족으로 분석 불가"]
        keywords   = f_kw.result(timeout=60)   or ["분석 중 오류"]
        geo_guides = f_geo.result(timeout=60)  or ["분석 중 오류"]

    result = {
        "competitors": competitors,
        "diagnoses":   diagnoses,
        "keywords":    keywords,
        "geo_guides":  geo_guides,
    }

    if use_cache:
        key = cache.make_key("strategy", target_url, question[:50], market_scope)
        cache.set(key, result, namespace="strategy")

    return result
