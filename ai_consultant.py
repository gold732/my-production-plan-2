import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다."""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}' 파라미터는 사용자가 [고정] 상태로 잠금해 두었으므로 수정이 불가능합니다."
    
    try:
        # [수정] AI가 입력한 값에 '%'나 공백이 포함된 경우 숫자만 추출하도록 정제
        cleaned_value = str(new_value).replace('%', '').strip()
        
        if parameter_key == 'enable_sub':
            val = cleaned_value.lower() in ['true', '1', 'yes', 'on']
        elif parameter_key == 'opt_mode':
            val = "선형계획법(LP)" if "LP" in cleaned_value or cleaned_value.lower() == 'false' else "정수계획법(IP)"
        elif parameter_key == 'demand_raw':
            val = cleaned_value
        else:
            val = float(cleaned_value)
            
        if 'pending_updates' not in st.session_state:
            st.session_state['pending_updates'] = {}
        st.session_state['pending_updates'][parameter_key] = val
        st.session_state['param_updated_by_ai'] = True
        st.session_state['skip_analysis'] = True
        
        return f"✅ 예약 성공: '{parameter_key}' -> '{val}'"
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패 ({str(e)})"


def get_ai_analysis(context_summary):
    """경영진 리포트 생성 (Lite-First 적용)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "API 키 없음"

    for key in available_keys:
        genai.configure(api_key=key)
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(model_id)
                prompt = f"분석 데이터: {context_summary}\n경영진 리포트를 JSON으로 작성하세요."
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                return json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            except Exception as e:
                last_error = str(e)
                # [수정] 유효하지 않은 키나 쿼터 초과 시 다음 키/모델 시도
                if any(msg in last_error.lower() for msg in ["api_key", "quota", "429", "invalid"]): continue
                return {"risk_level": "🚨 에러", "summary": f"오류 발생: {last_error}"}
    return {"risk_level": "🟡 분석 불가", "summary": f"키/할당량 부족: {last_error}"}


def get_ai_consultant(prompt, context_summary):
    """S&OP 전문가 AI 컨설턴트 (단위 가이드 강화)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 설정 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # [수정] ot_limit 단위(시간) 명시 및 복구 지능 강화
    system_instruction = f"""당신은 S&OP 전문가입니다. 
    [운영 데이터] {context_summary}
    [잠금 현황] {lock_status} (True 항목 수정 불가)
    
    ※ 필수 준수 사항:
    1. 'ot_limit'(연장근로 제한)은 퍼센트(%)가 아닌 **시간(Hr)** 단위입니다. (예: 50시간 설정 시 50 입력)
    2. Infeasible 상태 해결 시에는 단 한 번의 호출로 해가 나오도록 필요한 변수를 모두 조정하십시오.
    3. 수정한 값의 의미와 단위를 명확히 설명하십시오."""

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
                return "✅ 파라미터 업데이트를 예약했습니다."
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["api_key", "quota", "429", "invalid"]): continue
                else: return f"❌ AI 구동 오류: {last_error}"
                    
    return f"❌ 가동 실패: {last_error}"
