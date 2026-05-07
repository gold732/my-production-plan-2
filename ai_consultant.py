import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터(비용 설정, 공정 제약 설정, 운영 초기값 등)를 동적으로 변경합니다. 
    사용자가 특정 운영 목적(비용 절감, 가동률 과부하 해소 등)을 달성해달라고 지시하거나, 
    수학적으로 최적해를 찾을 수 없는(Infeasible) 상황을 해결하기 위해 이 도구를 호출하십시오.
    단, 사용자가 [고정] 체크박스를 켠 잠금 상태의 파라미터는 절대 변경할 수 없습니다.

    Args:
        parameter_key: 변경할 대상 파라미터의 고유 키 명칭. 
                       정확히 지정 가능한 종류: 
                       - 'opt_mode' (수리 알고리즘 유형 변경)
                       - 'enable_sub' (외주 하청 조율 여부 변경)
                       - 'std_time' (공정당 표준 공수), 'working_days' (월 가동일), 'ot_limit' (연장근로 한도)
                       - 'max_util' (최대 허용 가동률 제한 수치 %), 'min_inv' (최소 유지 재고량 수치 ea)
                       - 'max_cost' (최대 허용 총 운영 비용 상한 수치 천원)
                       - 'v_c_reg', 'v_c_ot', 'v_c_h', 'v_c_l', 'v_c_inv', 'v_c_back', 'v_c_mat', 'v_c_sub' (비용 인자 계수들)
                       - 'v_w_init', 'v_i_init', 'v_i_final' (운영 초기 설정값들)
        new_value: 반영하고자 하는 새로운 값의 문자열 표현. 
                   **[⚠️ 중요 준수 사항]**: 
                   - 'opt_mode' 제어 시 반드시 문자열인 '정수계획법(IP)' 또는 '선형계획법(LP)' 중 하나만 입력하십시오.
                   - 'enable_sub' 제어 시 반드시 문자열인 'True' 또는 'False'로 전달하십시오.
                   - 수치형 변수 제어 시 반드시 숫자로만 이루어진 문자열 기입하십시오.
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
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            
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
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            last_error = str(e)
            err_low = last_error.lower()
            if any(msg in err_low for msg in ["api_key", "api key", "unauthorized", "quota", "exhausted", "403", "401"]):
                continue
            else:
                return {
                    "risk_level": "🚨 시스템 오류",
                    "bottleneck_month": "연산 중단",
                    "summary": f"AI 분석 엔진 내부 런타임 오류가 감지되었습니다: {last_error}",
                    "recommendation": "시스템 관리자에게 에러 로그 확인을 요청하십시오."
                }
    return {
        "risk_level": "🟡 분석 불가", "bottleneck_month": "확인 불가",
        "summary": f"모든 API 키의 할당량이 소진되었습니다: {last_error}",
        "recommendation": "수동으로 대시보드 지표를 확인해 주십시오."
    }


def get_ai_consultant(prompt, context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets에 'GEMINI_KEYS'를 설정해주세요."
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
            
            system_instruction = f"""당신은 S&OP 생산관리 전문가이자 제어판을 완벽하게 통제하는 컨트롤 에이전트입니다.
            현재 상태: {context_summary}
            
            **[전략적 제어 및 복구 핵심 규칙]**
            1. **최적화 실패(Infeasible) 대응**: 현재 상태가 'Infeasible'이거나 '최적화 실패' 상태라면, 사용자가 묻지 않아도 즉시 해가 나올 수 있도록 'max_util'을 높이거나 'max_cost'를 상향하고, 혹은 'enable_sub'를 'True'로 변경하는 등 조치를 취하십시오.
            2. **가동률 현실화 가드**: 가동률 100%는 이론적으로 가능하나 실무적으로 불가능한 수치입니다. 가동률이 100%에 도달했다면 'max_util'을 90~95 수준으로 낮추도록 제안하거나 직접 조정하십시오.
            3. **재고 방어 가드 (`min_inv`)**: "각 월의 재고를 X 이상 유지하라"는 요구 시 즉시 `'min_inv'`를 조정하십시오.
            4. **예산 한도 가드 (`max_cost`)**: 비용 절감 요구 시 즉시 `'max_cost'`를 조정하십시오.
            5. **자율 즉시 실행**: 해가 나오지 않는 상황에서는 질문을 던지지 말고 목적을 달성할 수 있는 파라미터를 스스로 결정하여 즉시 `update_dashboard_parameter` 도구를 실행하십시오."""
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            try:
                response = chat.send_message(system_instruction + "\n\n사용자 질문: " + prompt)
                return response.text
            except Exception as accessor_error:
                if 'response' in locals() and hasattr(response, 'function_calls') and response.function_calls:
                    for call in response.function_calls:
                        if call.name == "update_dashboard_parameter":
                            args = dict(call.args)
                            result_str = update_dashboard_parameter(**args)
                            fallback_prompt = f"[인프라 가드] 도구 실행 결과: {result_str}\n변경된 설정을 기반으로 최적화를 재수행합니다. 상황을 브리핑하십시오."
                            response = chat.send_message(fallback_prompt)
                    return response.text
                else:
                    raise accessor_error
        except Exception as e:
            last_error = str(e)
            if any(msg in last_error.lower() for msg in ["api_key", "api key", "unauthorized", "quota", "exhausted", "403", "401"]):
                continue
            else:
                return f"❌ AI 구동 오류: {last_error}"
                
    return f"❌ AI 가동 실패 (최종 에러: {last_error})"
