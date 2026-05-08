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
        
        # AI가 파라미터를 직접 수정했으므로, 리로드 후 자동 분석 호출을 건너뜀 (RPD 절감)
        st.session_state['skip_analysis'] = True
        
        return f"✅ 예약 성공: '{parameter_key}' -> '{val}'"
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패 ({str(e)})"


def get_ai_analysis(context_summary):
    """경영진 리포트를 생성합니다. (Lite-First 적용)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "등록된 API 키가 없습니다."

    for key in available_keys:
        genai.configure(api_key=key)
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(model_id)
                prompt = f"""당신은 생산관리 전문가입니다. 제공된 데이터를 분석하여 JSON 리포트를 작성하세요.
                데이터: {context_summary}
                
                반환 형식(JSON):
                {{
                    "risk_level": "🟢 안전 / 🟡 주의 / 🚨 심각",
                    "bottleneck_month": "병목 월",
                    "summary": "핵심 요약 (2~3문장)",
                    "recommendation": "권고사항 (1~2문장)"
                }}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                raw_text = response.text.strip().replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["quota", "429", "limit"]):
                    continue
                return {"risk_level": "🚨 오류", "bottleneck_month": "-", "summary": f"에러: {last_error}", "recommendation": "확인 요청"}
    return {"risk_level": "🟡 제한", "bottleneck_month": "-", "summary": "RPD 초과", "recommendation": "수동 확인"}


def get_ai_consultant(prompt, context_summary):
    """S&OP 전문가 AI 컨설턴트: 상황에 따른 유연한 제약 조건을 적용합니다."""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 설정 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # [수정] 복구(Infeasible) 시에는 과감한 조정을, 일반 상황엔 절제를 지시
    system_instruction = f"""당신은 S&OP 생산관리 전문가이자 컨트롤 에이전트입니다.

[현재 운영 환경 데이터]
{context_summary}

[파라미터 잠금(Lock) 현황]
{lock_status} (True 항목은 절대 수정 금지)

[전략적 제어 규칙]
1. **문제 해결 우선 (가장 중요)**: 현재 상태가 'Infeasible(해 없음)'인 경우, RPD 절약을 위해 **단 한 번의 호출로 해법이 나올 수 있도록** 필요한 모든 변수(개수 제한 없음)를 과감하게 조정하십시오. 
2. **일반 운영 모드**: 해가 존재하는 상태에서 성능 최적화 요청 시에는 한 번에 2~3개 이내의 핵심 변수만 조정하십시오.
3. **논리적 우회 전략**: 특정 값이 잠겨있다면 즉시 대안 변수(예: 외주 허용, 가동일 상향 등)를 조합하십시오.
4. **결과 브리핑**: 수정한 파라미터와 그로 인해 예상되는 변화를 명확하게 설명하십시오."""

    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "등록된 API 키가 없습니다."

    for key in available_keys:
        genai.configure(api_key=key)
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(model_name=model_id, tools=[update_dashboard_parameter])
                chat = model.start_chat(enable_automatic_function_calling=True)
                response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
                
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            return part.text
                return "✅ 파라미터 조정을 완료했습니다. 대시보드를 확인하세요."
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["quota", "429", "limit"]):
                    continue
                else:
                    return f"❌ AI 구동 오류: {last_error}"
                    
    return f"❌ 가동 실패: {last_error}"
