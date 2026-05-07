import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다."""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}' 파라미터는 잠금 상태입니다."
    
    try:
        if parameter_key == 'enable_sub':
            val = new_value.lower() in ['true', '1', 'yes', 'on']
        elif parameter_key == 'opt_mode':
            val = "선형계획법(LP)" if "LP" in new_value or new_value.lower() == 'false' else "정수계획법(IP)"
        elif parameter_key == 'demand_raw':
            val = str(new_value)
        else:
            val = float(new_value)
            
        if 'pending_updates' not in st.session_state:
            st.session_state['pending_updates'] = {}
        st.session_state['pending_updates'][parameter_key] = val
        st.session_state['param_updated_by_ai'] = True
        # AI가 수정했으므로 다음 자동 분석은 건너뜀 (RPD 절감)
        st.session_state['skip_analysis'] = True
        
        return f"✅ 예약 성공: '{parameter_key}' -> '{val}'"
    except Exception as e:
        return f"❌ 오류: {str(e)}"


def get_ai_analysis(context_summary):
    """경영진 리포트를 생성합니다. (Lite-First 적용)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # Lite 모델을 1순위로 배치하여 RPD 절감
    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "API 키 없음"

    for key in available_keys:
        genai.configure(api_key=key)
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(model_id)
                prompt = f"""생산관리 전문가로서 데이터를 분석하여 JSON 리포트를 작성하세요.
                데이터: {context_summary}
                형식: {{"risk_level": "🟢 안전/🟡 주의/🚨 심각", "bottleneck_month": "월", "summary": "요약", "recommendation": "권고"}}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                return json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["quota", "429", "limit"]): continue
                return {"risk_level": "🚨 오류", "bottleneck_month": "-", "summary": f"에러: {last_error}", "recommendation": "관리자 확인"}
    return {"risk_level": "🟡 제한", "bottleneck_month": "-", "summary": "RPD 초과", "recommendation": "잠시 후 시도"}


def get_ai_consultant(prompt, context_summary):
    """전략 상담용 에이전트입니다. (Lite-First 및 호출 제한 적용)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ 설정 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # AI에게 최소한의 도구 호출만 하도록 강력 지시 (RPD 절감 핵심)
    system_instruction = f"""당신은 S&OP 전문가입니다. 
    [운영 데이터] {context_summary}
    [잠금 현황] {lock_status}
    
    ※ 규칙: 
    1. 효율적인 자원 사용을 위해 한 번에 **최대 2개까지만** 파라미터를 수정하십시오.
    2. 수정 후에는 반드시 어떤 값을 바꿨는지 짧고 명확하게 설명하십시오."""

    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "API 키 없음"

    for key in available_keys:
        genai.configure(api_key=key)
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_id, tools=[update_dashboard_parameter])
                chat = model.start_chat(enable_automatic_function_calling=True)
                response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
                
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text: return part.text
                return "✅ 조정을 완료했습니다."
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["quota", "429", "limit"]): continue
                return f"❌ AI 오류: {last_error}"
    return f"❌ 가동 실패: {last_error}"
