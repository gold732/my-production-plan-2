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
        # 입력값 정제 (단위 기호 제거 및 숫자 추출)
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
        
        # [RPD 최적화] AI 수정 시 자동 분석 리포트 생성을 1회 스킵하도록 설정
        st.session_state['skip_analysis'] = True
        
        return f"✅ 예약 성공: '{parameter_key}' -> '{val}' (다음 연산에 즉시 반영됩니다.)"
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패 ({str(e)})"


def get_ai_analysis(context_summary):
    """경영진 리포트를 생성합니다. (Lite-First 및 상세 프롬프트 복구)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "등록된 API 키가 없습니다."

    for key in available_keys:
        try:
            genai.configure(api_key=key)
            for model_id in models_to_try:
                try:
                    model = genai.GenerativeModel(model_id)
                    # [복구] 최초의 상세 페르소나 및 프롬프트 로직 100% 복구
                    prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 정밀하게 분석하여 경영진을 위한 종합 진단 보고서를 JSON 형태로 작성하세요.
                    데이터: {context_summary}
                    **경고 지침**: 특정 월의 가동률이 100%에 도달하면 이는 비현실적인 가동 계획(Burnout 리스크)임을 리포트에 반드시 명시하십시오.

                    반환 형식은 반드시 아래의 JSON 스키마 구조를 100% 준수해야 합니다:
                    {{
                        "risk_level": "🟢 안전 (가동률 적정 및 비용 안정)", "🟡 주의 (부분적 부하 또는 재고 불안정)", "🚨 심각 (가동률 과부하 및 운영 리스크)" 중 하나 선택,
                        "bottleneck_month": "가동률이 과부하 상태이거나 제약에 걸리는 핵심 월 (예: '3월', 없으면 '없음')",
                        "summary": "최적화 결과에 대한 핵심 요약 브리핑 문구 (2~3문장). 가동률 100% 발생 시 강력 경고 포함.",
                        "recommendation": "운영 효율성 개선 및 리스크 완화를 위한 실무적 핵심 권고사항 (1~2문장)"
                    }}"""
                    
                    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                    raw_text = response.text.strip().replace("```json", "").replace("```", "").strip()
                    return json.loads(raw_text)
                except Exception as e:
                    last_error = str(e)
                    if any(msg in last_error.lower() for msg in ["quota", "429", "invalid"]): continue
                    raise e
        except Exception as e:
            last_error = str(e)
            continue
            
    return {
        "risk_level": "🟡 분석 불가", "bottleneck_month": "확인 불가",
        "summary": f"모든 모델/키 할당량 소진: {last_error}",
        "recommendation": "수동으로 대시보드 지표를 확인해 주십시오."
    }


def get_ai_consultant(prompt, context_summary):
    """S&OP 전문가 AI 컨설턴트 (복구 지능 및 단위 가이드 강화)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 설정 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # [복구/강화] 상세 시스템 지시문 복구 및 단위 가이드 추가
    system_instruction = f"""당신은 S&OP 생산관리 전문가이자 제어판을 완벽하게 통제하는 컨트롤 에이전트입니다.

[현재 운영 데이터] {context_summary}
[파라미터 잠금 현황] {lock_status} (True는 수정 불가)

[전략적 제어 규칙]
1. **문제 해결 우선**: Infeasible(해 없음) 상태라면 단 한 번의 호출로 해가 나오도록 필요한 모든 변수를 과감하게 조정하십시오.
2. **단위 준수**: 'ot_limit'(연장근로 한도)는 퍼센트가 아닌 **시간(Hr)** 단위입니다. (예: 50시간은 50 입력)
3. **논리적 우회**: 특정 값이 고정되어 있다면 즉시 외주 허용(enable_sub)이나 가동일(working_days) 조정 등 대안을 찾으십시오.
4. **결과 브리핑**: 수정한 파라미터와 개선 효과를 논리적으로 설명하십시오."""

    models_to_try = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    last_error = "등록된 API 키가 없습니다."

    for key in available_keys:
        try:
            genai.configure(api_key=key)
            for model_id in models_to_try:
                try:
                    model = genai.GenerativeModel(model_name=model_id, tools=[update_dashboard_parameter])
                    chat = model.start_chat(enable_automatic_function_calling=True)
                    response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
                    
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'text') and part.text: return part.text
                    return "✅ 파라미터 조정을 예약했습니다."
                except Exception as e:
                    last_error = str(e)
                    if any(msg in last_error.lower() for msg in ["quota", "429", "invalid"]): continue
                    raise e
        except Exception: continue
                
    return f"❌ 가동 실패: {last_error}"
