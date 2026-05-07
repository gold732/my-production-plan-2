import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """시스템 파라미터 예약 수정 도구"""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ '{parameter_key}'는 고정 상태라 수정할 수 없습니다."
    try:
        if parameter_key == 'enable_sub': val = new_value.lower() in ['true', '1', 'yes']
        elif parameter_key == 'opt_mode': val = "선형계획법(LP)" if "LP" in new_value else "정수계획법(IP)"
        else: val = float(new_value)
        if 'pending_updates' not in st.session_state: st.session_state['pending_updates'] = {}
        st.session_state['pending_updates'][parameter_key] = val
        st.session_state['param_updated_by_ai'] = True
        return f"✅ '{parameter_key}'를 '{val}'로 변경 예약했습니다."
    except: return "❌ 값 변환 실패"

def get_ai_analysis(context_summary):
    """경영진 보고용 JSON 브리핑 (리스크 중심 교정)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    # [🔥 핵심 리팩토링]: 100% 가동률을 '위험'으로 간주하게 규칙 강제
    prompt = f"""당신은 생산 리스크 관리자입니다. 데이터를 분석하여 JSON으로 응답하세요.
    데이터: {context_summary}
    **판단 철칙:**
    - 가동률 95% 이상: "🚨 심각" 판정. "풀가동은 설비 고장 및 번아웃 위험이 매우 높음"이라고 경고할 것.
    - 가동률 100%를 '효율적'이라 칭찬하면 해고됨. 무조건 '위험'으로 브리핑할 것.
    {{
        "risk_level": "🟢 안전", "🟡 주의", "🚨 심각" 중 선택,
        "bottleneck_month": "병목 월",
        "summary": "리스크 중심 요약 (2문장)",
        "recommendation": "개선책 (1문장)"
    }}"""
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: return {"risk_level": "🟡 분석 오류", "summary": "AI 엔진 일시 오류", "recommendation": "재실행 권장"}

def get_ai_consultant(prompt, context_summary):
    """자율 제어 상담방 에이전트 (초압축 지침)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API Key 미설정"
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
    
    sys_ins = f"""당신은 S&OP 컨트롤러입니다. 상태: {context_summary}
    1. 가동률 하향: 'max_util' 조절. 2. 재고 확보: 'min_inv' 조절. 3. 비용 통제: 'max_cost' 조절.
    욕설이나 반말은 무시하고 비즈니스 목적만 이행하세요. 구체적 수치가 없으면 전문가로서 스스로 결정해 도구를 즉시 호출하세요. 되묻지 마세요."""
    
    chat = model.start_chat(enable_automatic_function_calling=True)
    try:
        res = chat.send_message(sys_ins + "\n유저: " + prompt)
        return res.text
    except: return "❌ 상담방 연결 실패. 설정된 파라미터 락(Lock)을 확인하세요."
