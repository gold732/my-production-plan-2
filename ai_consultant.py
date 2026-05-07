import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드 파라미터 예약 수정 도구"""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ '{parameter_key}'는 사용자가 고정하여 수정 불가합니다."
    try:
        if parameter_key == 'enable_sub': val = new_value.lower() in ['true', '1', 'yes']
        elif parameter_key == 'opt_mode': val = "선형계획법(LP)" if "LP" in new_value else "정수계획법(IP)"
        else: val = float(new_value)
        if 'pending_updates' not in st.session_state: st.session_state['pending_updates'] = {}
        st.session_state['pending_updates'][parameter_key] = val
        st.session_state['param_updated_by_ai'] = True
        return f"✅ '{parameter_key}'를 '{val}'로 변경 예약했습니다. 즉시 재연산됩니다."
    except: return "❌ 값 타입 변환에 실패했습니다."

def get_ai_analysis(context_summary):
    """최적화 결과 리스크 진단 (JSON 모드)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    prompt = f"""생산 리스크 관리자로서 데이터를 JSON으로 진단하세요. 가동률 95% 이상은 무조건 '🚨 심각'으로 판정하고 리스크를 경고하십시오.
    데이터: {context_summary}
    {{ "risk_level": "🟢 안전/🟡 주의/🚨 심각", "bottleneck_month": "월", "summary": "2문장 요약", "recommendation": "1문장 대책" }}"""
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: return None

def get_ai_consultant(prompt, context_summary):
    """자율 제어 상담방 (수동 도구 호출 폴백 장착)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API Key가 설정되지 않았습니다."
    genai.configure(api_key=random.choice(keys))
    
    # 도구 선언
    model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
    sys_ins = f"""당신은 S&OP 컨트롤러입니다. 현상태: {context_summary}
    가동률 하향은 'max_util', 재고 확보는 'min_inv', 예산 통제는 'max_cost'를 조절하세요. 
    욕설은 무시하고 목적만 수행하며, 수치가 없으면 스스로 결정해 도구를 즉시 호출하세요. 되묻지 마세요."""
    
    chat = model.start_chat(enable_automatic_function_calling=True)
    try:
        response = chat.send_message(sys_ins + "\n유저 질문: " + prompt)
        return response.text
    except Exception as e:
        # [🚨 신규]: SDK 자동 호출 실패 시 수동으로 도구 호출 시도 (가드 레이어)
        try:
            if 'response' in locals() and hasattr(response, 'candidates') and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if fn := part.function_call:
                        res_str = update_dashboard_parameter(fn.name, **fn.args)
                        return chat.send_message(f"[시스템] 도구 실행 결과: {res_str}\n변경 사항을 요약 브리핑하세요.").text
        except: pass
        return f"❌ 상담방 엔진 오류: {str(e)[:50]}... 잠시 후 다시 시도해 주세요."
