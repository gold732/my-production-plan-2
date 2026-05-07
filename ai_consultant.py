import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터(비용 설정, 공정 제약 설정, 운영 초기값 등)를 동적으로 변경합니다. 
    사용자가 특정 운영 목적(비용 절감, 가동률 과부하 해소 등)을 달성해달라고 지시하거나, 
    수학적으로 최적해를 찾을 수 없는(Infeasible) 상황을 해결하기 위해 이 도구를 호출하십시오.
    
   [💡 AI 필독 지침]
    1. 'max_util'(가동률)이나 'max_cost'(예산)가 고정(Lock)되어 변경할 수 없다면, 
       즉시 'working_days'(가동일)나 'ot_limit'(연장근로 한도) 같은 대안 변수를 수정하여 최적해를 찾으십시오.
    2. 특정 값이 고정되어 수정 거부 메시지가 나오면, 포기하지 말고 다른 '고정되지 않은' 변수를 조합하십시오.

    Args:
        parameter_key: 변경할 대상 파라미터의 고유 키 명칭. 
        new_value: 반영하고자 하는 새로운 값의 문자열 표현. 
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터 값이 최적 연산을 위해 '{val}'로 안전하게 버퍼에 대기 등록되었습니다."
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패 ({str(e)})"


def get_ai_analysis(context_summary):
    """경영진 리포트를 생성합니다. Flash 사용 불가 시 Lite로 자동 Fallback 합니다."""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 순차적 폴백 모델 리스트
    models_to_try = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']
    last_error = "등록된 API 키가 없습니다."

    for key in available_keys:
        genai.configure(api_key=key)
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(model_id)
                prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 정밀하게 분석하여 경영진을 위한 종합 진단 보고서를 JSON 형태로 작성하세요.
                데이터: {context_summary}
                **경고 지침**: 특정 월의 가동률이 100%에 도달하면 이는 비현실적인 가동 계획(Burnout 리스크)임을 리포트에 반드시 명시하십시오.

                반환 형식 JSON 스키마:
                {{
                    "risk_level": "🟢 안전 (가동률 적정 및 비용 안정)", "🟡 주의", "🚨 심각" 중 하나 선택,
                    "bottleneck_month": "병목 월 (예: '3월', 없으면 '없음')",
                    "summary": "최적화 결과 요약 (2~3문장)",
                    "recommendation": "리스크 완화 권고사항 (1~2문장)"
                }}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception as e:
                last_error = str(e)
                # 할당량 초과(Quota) 시 다음 모델이나 다음 키로 전환
                if any(msg in last_error.lower() for msg in ["api_key", "quota", "exhausted", "429", "403"]):
                    continue
                else:
                    # 기타 런타임 에러는 즉시 리포트
                    return {
                        "risk_level": "🚨 시스템 오류",
                        "bottleneck_month": "연산 중단",
                        "summary": f"AI 엔진 런타임 오류: {last_error}",
                        "recommendation": "시스템 관리자에게 문의하십시오."
                    }
    
    return {
        "risk_level": "🟡 분석 불가", "bottleneck_month": "확인 불가",
        "summary": f"모든 모델 및 API 키의 할당량이 소진되었습니다: {last_error}",
        "recommendation": "잠시 후 다시 시도하거나 수동으로 확인해 주십시오."
    }


def get_ai_consultant(prompt, context_summary):
    """전략 상담방용 에이전트입니다. Flash 사용 불가 시 Lite로 자동 Fallback 합니다."""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 설정 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    system_instruction = f"""당신은 S&OP 생산관리 전문가이자 컨트롤 에이전트입니다.
    [운영 데이터] {context_summary}
    [잠금 현황] {lock_status} (True 항목 수정 불가)
    변경 가능한(False) 변수들을 조합하여 문제를 해결하고, 수정 후 논리적 근거를 설명하십시오."""

    models_to_try = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']
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
                return "✅ 파라미터 조정을 완료했습니다."
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["api_key", "quota", "exhausted", "429", "403"]):
                    continue
                else:
                    return f"❌ AI 구동 오류: {last_error}"
                    
    return f"❌ 모든 모델 가동 실패 (최종 에러: {last_error})"
