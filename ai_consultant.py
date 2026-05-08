import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드 파라미터를 동적으로 변경합니다. (UI 범위 보호 로직 포함)"""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}'는 잠금 상태입니다."
    
    try:
        # 단위 기호 제거 및 숫자 정제
        cleaned_value = str(new_value).replace('%', '').replace('시간', '').replace('hr', '').strip()
        
        if parameter_key == 'enable_sub':
            val = cleaned_value.lower() in ['true', '1', 'yes', 'on']
        elif parameter_key == 'opt_mode':
            val = "선형계획법(LP)" if "LP" in cleaned_value or cleaned_value.lower() == 'false' else "정수계획법(IP)"
        elif parameter_key == 'demand_raw':
            val = cleaned_value
        else:
            temp_val = float(cleaned_value)
            # [안전 가드] UI 슬라이더 한계를 초과하여 시스템이 터지는 것 방지
            if parameter_key == 'ot_limit':
                val = max(0.0, min(temp_val, 100.0)) # 0~100 Hr
            elif parameter_key == 'working_days':
                val = int(max(1.0, min(temp_val, 30.0))) # 1~30 일
            elif parameter_key == 'max_util':
                val = max(1.0, min(temp_val, 100.0)) # 1~100 %
            else:
                val = temp_val
            
        if 'pending_updates' not in st.session_state:
            st.session_state['pending_updates'] = {}
        st.session_state['pending_updates'][parameter_key] = val
        st.session_state['param_updated_by_ai'] = True
        st.session_state['skip_analysis'] = True
        
        return f"✅ 예약 성공: '{parameter_key}' -> '{val}'"
    except Exception as e:
        return f"❌ 오류: {str(e)}"

def get_ai_analysis(context_summary):
    """경영진 리포트 생성 (Lite-First 및 정교한 프롬프트 보존)"""
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
                prompt = f"""생산관리 전문가로서 데이터를 분석하여 JSON 리포트를 작성하세요.
                데이터: {context_summary}
                가동률 100% 발생 시 Burnout 리스크를 반드시 경고하십시오.
                
                형식: {{"risk_level": "🟢 안전/🟡 주의/🚨 심각", "bottleneck_month": "월", "summary": "요약", "recommendation": "권고"}}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                raw_text = response.text.strip().replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception: continue
    return {"risk_level": "🟡 분석 불가", "summary": "잠시 후 시도해 주십시오."}

def get_ai_consultant(prompt, context_summary):
    """S&OP 전문가 AI (UI 제약 인지 및 원샷 해결)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # [수정] AI에게 UI 슬라이더의 물리적 한계치를 교육함
    system_instruction = f"""당신은 S&OP 전문가입니다. 
    [운영 데이터] {context_summary}
    [잠금 현황] {lock_status} (True 수정 불가)
    
    [⚠️ 필수 UI 제약 조건]
    - 'ot_limit'(연장근로): 0 ~ 100 Hr (100 초과 시 시스템 오류 발생)
    - 'working_days'(가동일): 1 ~ 30 일
    - 'max_util'(가동률 상한): 1 ~ 100 %
    
    ※ 문제 해결 전략:
    1. Infeasible(해 없음) 상태라면 찔끔거리지 말고 단번에 해가 나오도록 가능한 모든 변수를 수정하십시오.
    2. 특정 값이 UI 상한(예: OT 100시간)에 도달했는데도 해가 없다면, 즉시 'enable_sub'(외주)를 켜거나 'working_days'를 늘리십시오.
    3. 모든 수정은 위 [UI 제약 조건] 범위 내에서만 수행하십시오."""

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
                if any(msg in last_error.lower() for msg in ["quota", "429", "invalid"]): continue
                return f"❌ AI 오류: {last_error}"
    return f"❌ 가동 실패: {last_error}"
