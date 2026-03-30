import os
import time
import json
import hashlib
import concurrent.futures
import difflib
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st
from openai import OpenAI

# =========================
# 🔐 환경 설정
# =========================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# =========================
# 🧠 캐시
# =========================
CACHE = {}

def _hash_key(prompt: str, model: str):
    return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()

def cached_llm_call(call_fn, prompt: str, model: str, ttl=3600):
    key = _hash_key(prompt, model)

    if key in CACHE:
        data, ts = CACHE[key]
        if time.time() - ts < ttl:
            return data

    try:
        result = call_fn(prompt)
        CACHE[key] = (result, time.time())
        return result
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return ""

# =========================
# 🤖 GPT 호출
# =========================
def call_gpt_safe(prompt, model="gpt-4o-mini"):
    def _call(p):
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": p}],
            max_tokens=300,
            temperature=0.5,
        )
        return res.choices[0].message.content.strip()

    return cached_llm_call(_call, prompt, model)

# =========================
# 🔍 브랜드 감지
# =========================
def build_variants(domain: str, brand: str):
    base = domain.split(".")[0]

    variants = set([
        base.lower(),
        domain.lower(),
        brand.lower(),
        brand.replace(" ", "").lower()
    ])

    return list(variants)

def is_brand_mentioned(text: str, variants: list[str], threshold=0.75):
    text = text.lower()

    for v in variants:
        if v in text:
            return True

        for word in text.split():
            score = difflib.SequenceMatcher(None, word, v).ratio()
            if score > threshold:
                return True

    return False

# =========================
# ❓ 질문 생성
# =========================
def generate_questions(brand, industry):
    prompt = f"{industry} 분야에서 {brand} 관련 실제 질문 5개 생성"
    res = call_gpt_safe(prompt)
    qs = [q.strip("- ").strip() for q in res.split("\n") if "?" in q]
    return qs[:5]

# =========================
# 🧪 시뮬레이션
# =========================
def run_simulation(question, domain, brand, n=20):
    variants = build_variants(domain, brand)

    def single():
        prompt = f"질문: {question}\n답변:"
        res = call_gpt_safe(prompt)
        return is_brand_mentioned(res, variants)

    hits = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(single) for _ in range(n)]

        for f in futures:
            try:
                if f.result():
                    hits += 1
            except:
                pass

    rate = round(hits / n * 100, 1)
    return {"hits": hits, "total": n, "rate": rate}

# =========================
# 🧠 전략 분석
# =========================
def run_strategy(question, brand):
    prompts = {
        "진단": f"{brand}이 '{question}'에서 약한 이유 3가지",
        "키워드": f"{brand} 관련 블루오션 키워드 5개",
        "콘텐츠": f"{question} 콘텐츠 전략 3가지"
    }

    results = {}

    def run(p):
        return call_gpt_safe(p)

    with concurrent.futures.ThreadPoolExecutor() as ex:
        futs = {k: ex.submit(run, v) for k, v in prompts.items()}

        for k, f in futs.items():
            try:
                results[k] = f.result()
            except:
                results[k] = ""

    return results

# =========================
# 💾 결과 저장
# =========================
def save_report(data):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{REPORT_DIR}/report_{ts}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filename

# =========================
# 📄 텍스트 리포트 생성
# =========================
def generate_text_report(data):
    lines = []
    lines.append(f"브랜드: {data['brand']}")
    lines.append(f"도메인: {data['domain']}")
    lines.append("="*40)

    for item in data["results"]:
        lines.append(f"\n[질문] {item['question']}")
        lines.append(f"점유율: {item['simulation']['rate']}%")

        for k, v in item["strategy"].items():
            lines.append(f"\n{ k }:\n{ v }")

    return "\n".join(lines)

# =========================
# 🎨 UI
# =========================
st.set_page_config(page_title="AI SEO Analyzer", layout="wide")
st.title("🚀 AI SEO 분석기")

brand = st.text_input("브랜드명", "OpenAI")
domain = st.text_input("도메인", "openai.com")
industry = st.text_input("산업", "AI")

run = st.button("분석 시작")

if run:
    report_data = {
        "brand": brand,
        "domain": domain,
        "created_at": str(datetime.now()),
        "results": []
    }

    questions = generate_questions(brand, industry)

    for q in questions:
        st.subheader(q)

        sim = run_simulation(q, domain, brand)
        st.write(sim)

        strategy = run_strategy(q, brand)

        for k, v in strategy.items():
            st.markdown(f"**{k}**")
            st.write(v)

        report_data["results"].append({
            "question": q,
            "simulation": sim,
            "strategy": strategy
        })

        st.divider()

    # 💾 저장
    filepath = save_report(report_data)
    st.success(f"저장 완료: {filepath}")

    # 📥 다운로드
    json_str = json.dumps(report_data, ensure_ascii=False, indent=2)
    st.download_button("📥 JSON 다운로드", json_str, file_name="report.json")

    text_report = generate_text_report(report_data)
    st.download_button("📄 텍스트 리포트 다운로드", text_report, file_name="report.txt")
