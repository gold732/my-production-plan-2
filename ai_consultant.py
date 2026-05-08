import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """[상담용] 파라미터를 버퍼에 등록하여 안전하게 변경합니다."""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}'는 고정 상태입니다."
    
    try:
        cleaned_value = str(new_value).replace('%', '').strip()
        if parameter_key == 'enable_sub':
            val = cleaned_value.lower() in ['true', '1', 'yes', 'on']
        else:
            val = float(cleaned_value)
            
        if 'pending_updates' not in st.session_state:
            st.session_state['pending_updates'] = {}
        st.session_state['pending_updates'][parameter_key] = val
        st.session_state['param_updated_by_ai'] = True
        return f"✅ 예약 성공: {parameter_key} -> {val}"
    except Exception as e:
        return f"❌ 오류: {str(e)}"

def get_ai_analysis(context_summary):
    """결과 데이터 분석 (Flash-Lite 사용으로 RPD 절감)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    prompt = f"""당신은 S&OP 전문가입니다. 데이터를 보고 JSON 리포트를 작성하세요.
    데이터: {context_summary}
    형식: {{"risk_level": "🟢 안전/🟡 주의/🚨 심각", "bottleneck_month": "월", "summary": "요약", "recommendation": "제언"}}"""
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(raw_text)
    except:
        return {"risk_level": "🟡 확인", "summary": "연산 완료", "recommendation": "수동 모니터링 요망"}

def get_ai_consultant(prompt, context_summary):
    """상담 전문 에이전트 (RPD 관리를 위해 Flash 사용)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정 필요"
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel(model_name='gemini-2.5-flash', tools=[update_dashboard_parameter])
    chat = model.start_chat(enable_automatic_function_calling=True)
    response = chat.send_message(f"데이터: {context_summary}\n\n질문: {prompt}")
    return response.text
