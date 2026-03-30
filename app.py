import os
import time
import json
import hashlib
import concurrent.futures
import difflib
from datetime import datetime
import streamlit as st
from openai import OpenAI
import requests

# =========================
# 📁 설정
# =========================
REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# =========================
# 🧠 캐시
# =========================
CACHE = {}

def _hash_key(prompt: str, model: str):
    return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()

def cached_call(call_fn, prompt: str, model: str, ttl=3600):
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
        print(f"[ERROR:{model}] {e}")
        return ""

# =========================
# 🔐 API KEY UI
# =========================
st.sidebar.title("🔐 API 설정")

openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

if openai_key:
    st.session_state["openai_key"] = openai_key

if gemini_key:
    st.session_state["gemini_key"] = gemini_key

# 상태 표시
if "openai_key" in st.session_state:
    st.sidebar.success("✅ GPT 연결됨")

if "gemini_key" in st.session_state:
    st.sidebar.success("✅ Gemini 연결됨")

# =========================
# 🤖 GPT 호출
# =========================
def call_gpt(prompt):
    if "openai_key" not in st.session_state:
        return ""

    client = OpenAI(api_key=st.session_state["openai_key"])

    def _call(p):
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": p}],
            max_tokens=300,
            temperature=0.5,
        )
        return res.choices[0].message.content.strip()

    return cached_call(_call, prompt, "gpt")

# =========================
# 🤖 Gemini 호출
# =========================
def call_gemini(prompt):
    if "gemini_key" not in st.session_state:
        return ""

    def _call(p):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={st.session_state['gemini_key']}"
        body = {"contents": [{"parts": [{"text": p}]}]}

        res = requests.post(url, json=body)

        if res.status_code == 200:
            return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        return ""

    return cached_call(_call, prompt, "gemini")

# =========================
# 🔍 브랜드 감지
# =========================
def build_variants(domain, brand):
    base = domain.split(".")[0]
    return list(set([
        base.lower(),
        domain.lower(),
        brand.lower(),
        brand.replace(" ", "").lower()
    ]))

def is_brand_mentioned(text, variants):
    text = text.lower()

    for v in variants:
        if v in text:
            return True

        for word in text.split():
            if difflib.SequenceMatcher(None, word, v).ratio() > 0.75:
                return True

    return False

# =========================
# ❓ 질문 생성
# =========================
def generate_questions(brand, industry):
    prompt = f"{industry}에서 {brand} 관련 질문 5개 생성"
    res = call_gpt(prompt) or call_gemini(prompt)
    return [q.strip("- ").strip() for q in res.split("\n") if "?" in q][:5]

# =========================
# 🧪 시뮬레이션 (핵심)
# =========================
def run_simulation(question, domain, brand, n=10):
    variants = build_variants(domain, brand)

    use_gpt = "openai_key" in st.session_state
    use_gemini = "gemini_key" in st.session_state

    def single():
        prompt = f"질문: {question}\n답변:"
        hit = 0
        total = 0

        if use_gpt:
            res = call_gpt(prompt)
            total += 1
            if is_brand_mentioned(res, variants):
                hit += 1

        if use_gemini:
            res = call_gemini(prompt)
            total += 1
            if is_brand_mentioned(res, variants):
                hit += 1

        return hit, total

    hits = 0
    total = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(single) for _ in range(n)]

        for f in futures:
            try:
                h, t = f.result()
                hits += h
                total += t
            except:
                pass

    rate = round((hits / total * 100), 1) if total > 0 else 0
    return hits, total, rate

# =========================
# 🧠 전략
# =========================
def run_strategy(question, brand):
    prompt = f"{brand}이 '{question}'에서 노출을 높이는 전략 3가지"
    return call_gpt(prompt) or call_gemini(prompt)

# =========================
# 💾 저장
# =========================
def save_report(data):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{REPORT_DIR}/report_{ts}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path

# =========================
# 📄 텍스트 리포트
# =========================
def generate_text_report(data):
    lines = []
    lines.append(f"브랜드: {data['brand']}")
    lines.append("=" * 40)

    for item in data["results"]:
        lines.append(f"\nQ: {item['question']}")
        lines.append(f"점유율: {item['rate']}%")

    return "\n".join(lines)

# =========================
# 🎨 UI
# =========================
st.title("🚀 AI SEO (GEO) 분석기")

brand = st.text_input("브랜드명", "OpenAI")
domain = st.text_input("도메인", "openai.com")
industry = st.text_input("산업", "AI")

if st.button("분석 시작"):

    # 👉 최소 1개 키 필요
    if "openai_key" not in st.session_state and "gemini_key" not in st.session_state:
        st.error("최소 하나의 API 키(OpenAI 또는 Gemini)가 필요합니다.")
        st.stop()

    report = {
        "brand": brand,
        "created_at": str(datetime.now()),
        "results": []
    }

    questions = generate_questions(brand, industry)

    for q in questions:
        st.subheader(f"❓ {q}")

        hits, total, rate = run_simulation(q, domain, brand)

        col1, col2, col3 = st.columns(3)
        col1.metric("노출 횟수", hits)
        col2.metric("총 시도", total)
        col3.metric("점유율 (%)", rate)

        strategy = run_strategy(q, brand)
        st.write(strategy)

        report["results"].append({
            "question": q,
            "hits": hits,
            "total": total,
            "rate": rate
        })

        st.divider()

    path = save_report(report)
    st.success(f"저장됨: {path}")

    st.download_button("📥 JSON 다운로드",
                       json.dumps(report, ensure_ascii=False, indent=2),
                       file_name="report.json")

    st.download_button("📄 TXT 다운로드",
                       generate_text_report(report),
                       file_name="report.txt")
