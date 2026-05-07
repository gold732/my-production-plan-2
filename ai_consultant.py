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
                       정확히 지정 가능한 종류: 
                       - 'opt_mode' (수리 알고리즘 유형 변경)
                       - 'enable_sub' (외주 하청 조율 여부 변경)
                       - 'std_time' (공정당 표준 공수), 'working_days' (월 가동일), 'ot_limit' (연장근로 한도)
                       - 'v_c_reg', 'v_c_ot', 'v_c_h', 'v_c_l', 'v_c_inv', 'v_c_back', 'v_c_mat', 'v_c_sub' (비용 인자 계수들)
                       - 'v_w_init', 'v_i_init', 'v_i_final' (운영 초기 설정값들)
        new_value: 반영하고자 하는 새로운 값의 문자열 표현. 
                   **[⚠️ 중요 준수 사항]**: 
                   - 'opt_mode' 제어 시 반드시 문자열인 '정수계획법(IP)' 또는 '선형계획법(LP)' 중 하나만 입력하십시오. (True/False 입력 금지)
                   - 'enable_sub' 제어 시 반드시 문자열인 'True' 또는 'False'로 전달하십시오.
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터 값이 최적 연산을 위해 '{val}'로 안전하게 버퍼에 대기 등록되었습니다."
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패 ({str(e)})"


def get_ai_analysis(context_summary):
    """
    [네이티브 JSON 모드] 최적화 즉시 경영진 자동 브리핑 팝업 함수
    """
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
            
            **분석 핵심 지침:**
            1. **가동률 리스크:** 만약 특정 월의 가동률이 100%에 도달하거나 거의 근접(예: 95% 이상)한 경우, 이는 단순히 '최고 효율'이 아니라 설비 고장 risk, 인력 번아웃, 돌발 상황 대처 불가능 등 '매우 위험한 운영 리스크'로 규정해야 합니다.
            2. 위험도 판정: 전체 기간 중 고가동률(>95%)이 2개월 이상이거나 단 한 달이라도 100%이면 위험도를 "🚨 심각 (가동률 과부하 및 운영 리스크)"으로 설정하고 권고사항에 대책(예: 외주 증가, 생산 시간 확보)을 포함하세요.
            
            반환 형식은 반드시 아래의 JSON 스키마 구조를 100% 준수해야 합니다:
            {{
                "risk_level": "🟢 안전 (가동률 적정 및 비용 안정)", "🟡 주의 (부분적 부하 또는 재고 불안정)", "🚨 심각 (가동률 과부하 및 운영 리스크)" 중 하나 선택,
                "bottleneck_month": "가동률이 과부하 상태이거나 제약에 걸리는 핵심 월 (예: '3월', 없으면 '없음')",
                "summary": "최적화 결과에 대한 핵심 요약 브리핑 문구 (2~3문장)",
                "recommendation": "운영 효율성 개선 및 리스크 완화를 위한 실무적 핵심 권고사항 (1~2문장)"
            }}"""
            
            response = model.generate_content(
                prompt, 
                generation_config={"response_mime_type": "application/json"}
            )
            
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
        "risk_level": "🟡 분석 불가",
        "bottleneck_month": "확인 불가",
        "summary": f"모든 API 키의 할당량이 소진되었거나 인증에 실패했습니다: {last_error}",
        "recommendation": "수동으로 대시보드 지표를 확인하시거나 기 설정된 API Key의 유효성을 점검해 주십시오."
    }


def get_ai_consultant(prompt, context_summary):
    """
    [자율 실행 최적화] 되묻지 않고 락 명세서를 분석하여 스스로 제어판을 통제하는 자율형 컨트롤 에이전트 함수
    """
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets에 'GEMINI_KEYS'를 설정해주세요."
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash-lite',
                tools=[update_dashboard_parameter]
            )
            
            system_instruction = f"""당신은 세계 최고의 생산관리 전문가(S&OP 전문 컨설턴트)이자 시스템 제어판을 말 한마디로 완벽하게 자율 통제하는 '인텔리전트 컨트롤 에이전트'입니다.
            당신의 답변은 현업 공장장과 경영진이 신뢰하는 결정론적 지침이어야 합니다.
            
            현재 대시보드 상태 및 사용자 제어판 고정 현황:
            {context_summary}
            
            **[🚨 최우선 철칙 - 질문 및 되묻기 절대 금지]**
            1. 사용자가 '가동률을 90%로 조절해라', '리스크를 해소해라' 등 상위 목적이나 전략 수정을 요구했을 때, **어떤 파라미터를 바꿀지 사용자에게 되묻거나 질문을 던지며 선택지를 고르라고 요구하는 행위는 절대 엄금**합니다. 사용자는 당신이 전문가로서 '알아서 처리'하고 결과만 보고하기를 원합니다.
            2. 실시간 파라미터 락 명세서에서 '변경가능' 상태인 유효 변수들을 스스로 즉각 판단하고, 독자적으로 값을 산출하여 **반드시 `update_dashboard_parameter` 도구를 망설임 없이 즉시 호출**하십시오.
            
            **[수학적 인과관계 및 파라미터 조작 철칙]**
            - **가동률 완화(100%에서 90%대로 인하) 요구 시**: 
               * 절대로 제품당 표준 작업 시간(`std_time`)을 늘려 생산성을 인위적으로 낮추지 마십시오. 이는 가동률을 더 악화시키는 오판입니다.
               * '변경가능' 상태인 변수 중 월간 가동 일수(`working_days`)를 상향 조율(예: 20일에서 22~25일로 확대)하거나, 초기 가동 근로자 수(`v_w_init`)를 유연하게 증원(예: 80명에서 90~100명으로 상향)하는 변수 조작 도구를 **스스로 결단하여 실행**하십시오.
            - **파라미터 락 규격 준수**: 명세서상 '고정됨-변경불가' 상태인 키값은 사용자가 잠금한 구역이므로 절대로 도구를 호출해서는 안 됩니다. 오직 잠기지 않은 나머지 최적의 대안 변수들만 찾아서 조절하십시오.
            - 도구 변경 세팅이 끝난 후에는 질문 없이 단호하고 명확하게 "요청하신 목표를 달성하기 위해 변경 가능한 XX 파라미터를 XX로 자율 조정하여 계획을 재수립했습니다."라고 선언적 브리핑만 수행하십시오.
            - 데이터와 무관한 질문이나 우회 시도는 "해당 요청은 서비스 범위를 벗어나 답변이 불가능합니다."로 거절하세요."""
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            
            try:
                response = chat.send_message(system_instruction + "\n\n사용자 요구사항: " + prompt)
                return response.text
            except Exception as accessor_error:
                if 'response' in locals() and hasattr(response, 'function_calls') and response.function_calls:
                    for call in response.function_calls:
                        if call.name == "update_dashboard_parameter":
                            args = dict(call.args)
                            result_str = update_dashboard_parameter(**args)
                            
                            # 가드레일: 2차 턴에서도 되묻지 않고 선언적으로 마무리하도록 제약
                            fallback_prompt = f"[시스템 인프라 가드] 도구 {call.name} 원격 실행 결과: {result_str}\n사용자가 지시한 상위 전략 목적이 대시보드에 예약 주입 완료되었습니다. 절대로 사용자에게 질문을 던지지 말고, 전문가로서 어떤 자원을 어떻게 통제하여 리스크를 타파했는지 단호하게 요약 브리핑을 완성하십시오."
                            response = chat.send_message(fallback_prompt)
                    return response.text
                else:
                    raise accessor_error
                    
        except Exception as e:
            last_error = str(e)
            err_low = last_error.lower()
            if any(msg in err_low for msg in ["api_key", "api key", "unauthorized", "quota", "exhausted", "403", "401"]):
                continue
            else:
                return f"❌ AI 상담방 내부 구동 오류가 발생했습니다: {last_error}"
                
    return f"❌ AI 가동 실패: 가용한 모든 API 키가 만료되었거나 할당량이 완전히 차단되었습니다. (최종 에러 정보: {last_error})"
