import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드 파라미터를 동적으로 변경합니다."""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}'는 잠금 상태입니다."
    
    try:
        # 단위 기호 및 공백 제거 로직 보존
        cleaned_value = str(new_value).replace('%', '').replace('시간', '').replace('hr', '').strip()
        
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
        
        # AI가 수정했으므로 다음 자동 분석은 건너뜀 (RPD 1회 절감)
        st.session_state['skip_analysis'] = True
        
        return f"✅ 예약 성공: '{parameter_key}' -> '{val}'"
    except Exception as e:
        return f"❌ 오류: {str(e)}"

def get_ai_analysis(context_summary):
    """경영진 리포트 생성 (최초의 정교한 프롬프트 100% 복구)"""
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
                # [복구] 유실되었던 상세 분석 지침 및 경고 로직 재삽입
                prompt = f"""당신은 생산관리 전문가입니다. 최적화 결과 데이터를 분석하여 경영진 리포트를 JSON으로 작성하세요.
                데이터: {context_summary}
                **필수 지침**: 가동률 100% 도달 시 Burnout 리스크를 반드시 명시할 것.
                
                형식 준수:
                {{
                    "risk_level": "🟢 안전 / 🟡 주의 / 🚨 심각",
                    "bottleneck_month": "병목 월 명시",
                    "summary": "핵심 요약 (2~3문장). 가동률 100% 시 강력 경고 포함.",
                    "recommendation": "리스크 완화 권고사항 (1~2문장)"
                }}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                raw_text = response.text.strip().replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["quota", "429", "invalid"]): continue
                return {"risk_level": "🚨 에러", "bottleneck_month": "-", "summary": f"오류: {last_error}", "recommendation": "관리자 확인"}
    return {"risk_level": "🟡 제한", "bottleneck_month": "-", "summary": "RPD 초과", "recommendation": "잠시 후 시도"}

def get_ai_consultant(prompt, context_summary):
    """S&OP 전문가 AI (원샷 해결 로직 적용)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # [수정] RPD 절감을 위해 '한 번에 다 고쳐서 끝내라'고 지침 변경
    system_instruction = f"""당신은 S&OP 전문가 컨트롤 에이전트입니다.
    [운영 데이터] {context_summary}
    [잠금 현황] {lock_status} (True 수정 불가)
    
    ※ RPD(요청횟수) 절감 규칙:
    1. Infeasible(해 없음) 상태일 경우, 찔끔찔끔 바꾸지 말고 **단 한 번의 호출로 해가 나올 수 있도록** 필요한 모든 변수를 과감하게 조정하십시오.
    2. 'ot_limit'(연장근로 제한)은 반드시 **시간(Hr)** 단위로 입력하십시오. (예: 50시간은 50)
    3. 수정한 값들과 그로 인한 개선 기대 효과를 명확히 설명하십시오."""

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
                return "✅ 파라미터 업데이트가 예약되었습니다."
            except Exception as e:
                last_error = str(e)
                if any(msg in last_error.lower() for msg in ["quota", "429", "invalid"]): continue
                return f"❌ AI 오류: {last_error}"
    return f"❌ 가동 실패: {last_error}"
