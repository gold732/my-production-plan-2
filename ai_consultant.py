import streamlit as st
import google.generativeai as genai
import random
import json

# 파라미터 업데이트 도구는 수동 상담 시에만 사용
def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드 파라미터를 안전하게 변경합니다."""
    # (이미 검증된 안전 가드 로직 보존)
    # ... 기존 코드 동일 ...
    return f"✅ 예약 성공: {parameter_key} -> {new_value}"

def get_ai_analysis(context_summary):
    """코드가 찾아낸 결과에 대해 전문가적 식견으로 진단만 수행합니다. (RPD 절감)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel('gemini-2.5-flash-lite') # 분석은 가성비 모델로 충분
    
    prompt = f"""당신은 S&OP 전략가입니다. 코드가 산출한 결과를 보고 경영진 리포트를 작성하세요.
    데이터: {context_summary}
    형식: {{"risk_level": "🟢 안전/🟡 주의/🚨 심각", "summary": "분석 결과 요약", "recommendation": "전략적 제언"}}"""
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text.strip())
    except:
        return {"risk_level": "🟡 확인 필요", "summary": "데이터 수신 완료", "recommendation": "수동 모니터링"}

def get_ai_consultant(prompt, context_summary):
    """사용자와의 전략 상담 기능에만 집중합니다."""
    # (기존 상담 로직 보존)
    # ... 기존 코드 동일 ...
    return "✅ 상담 완료"
