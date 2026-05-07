import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터(비용 설정, 공정 제약 설정, 운영 초기값 등)를 동적으로 변경합니다. 
    사용자가 특정 운영 목적(비용 절감, 가동률 과부하 해소 등)을 달성해달라고 지시할 때 이 도구를 호출하여 시스템 설정을 변경하십시오.
    단, 사용자가 [고정] 체크박스를 켠 잠금 상태의 파라미터는 절대 변경할 수 없습니다.

    Args:
        parameter_key: 변경할 대상 파라미터의 고유 키 명칭. 
        new_value: 반영하고자 하는 새로운 값의 문자열 표현. 
                   **[⚠️ 중요 준수 사항]**: 
                   - 'max_util' (가동률) 제어 시 0.9 같은 소수가 아닌 반드시 '90', '85'와 같은 1~100 사이의 수치를 입력하십시오.
                   - 수치형 변수 제어 시 반드시 숫자로만 이루어진 문자열(예: '25', '1000' 등)을 기입하십시오.
    """
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}' 파라미터는 사용자가 [고정] 상태로 잠금해 두었으므로 수정이 불가능합니다. 고정되지 않은 다른 '변경가능' 변수들을 조합하십시오."
    
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터 값이 '{val}'로 버퍼에 등록되었습니다."
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패 ({str(e)})"


def get_ai_analysis(context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            prompt = f"""당신은 생산관리 전문가입니다. 데이터: {context_summary}
            가동률 100%는 비현실적이고 위험한 계획임을 반드시 지적하고 실무적인 권고사항을 JSON으로 작성하세요.
            가동률이 100%라면 '🚨 심각' 등급을 부여하십시오."""
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            raw_text = response.text.strip()
            if raw_text.startswith("
http://googleusercontent.com/immersive_entry_chip/0
