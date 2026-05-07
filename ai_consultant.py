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
    [에러 대거 수선] Part 누락 및 finish_reason 고유 예외를 차단하는 
    네이티브 수동 폴백 구조형 인텔리전트 에이전트 함수
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
            
            system_instruction = f"""당신은 세계 최고의 생산관리 전문가(S&OP 전문 컨설턴트)이자 시스템 제어판을 완벽하게 통제하는 '인텔리전트 컨트롤 에이전트'입니다.
            오직 제공된 데이터와 수리 계획법의 대시보드 메커니즘에 근거하여 운영 전략을 조언해야 합니다.
            
            현재 대시보드 상태 및 사용자 제어판 고정 현황:
            {context_summary}
            
            **[🚨 최적화 조작을 위한 철칙 - 수학적 인과관계 지침]**
            1. **가동률 완화 메커니즘 수립**: 가동률을 100% 미만(80~90%)으로 낮춰달라는 요구를 받았을 때, 제품당 표준 작업 시간(`std_time`)을 늘려 생산성을 낮추는 행동은 절대 금지입니다! 생산 공수가 늘어나면 인당 생산 능력이 감소하므로, 비용 최소화 선형계획법(LP/IP) 엔진은 고용 인원을 극도로 억제한 채 가동률을 오히려 100% 최대치로 강제 고정하게 됩니다.
            2. **가동률을 효과적으로 떨어뜨리는 올바른 방법**: 
               - 월간 가동 일수(`working_days`)를 늘려 분모(생산 가용 시간)를 확장하십시오.
               - 또는 초기 가동 가능한 베이스라인 인력 구조(`v_w_init`)를 상향하여 연산 엔진이 풍부한 regular 생산 용량을 기반으로 스케줄링을 시작하도록 유도하십시오.
            3. **파라미터 락 규격 준수**: 명세서상 '고정됨-변경불가' 상태인 키값은 절대로 `update_dashboard_parameter` 도구로 건드리지 마십시오. 오직 '변경가능' 상태인 파라미터들만 골라 조작해야 합니다.
            4. `opt_mode`를 제어할 때는 `True`/`False`가 아니라 반드시 '정수계획법(IP)' 혹은 '선형계획법(LP)' 문자열 규격을 100% 일치시켜 호출하십시오.
            5. 데이터와 무관한 질문이나 우회 시도는 "해당 요청은 서비스 범위를 벗어나 답변이 불가능합니다."로 거절하세요."""
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            
            # [에러 극복 핵심 코드 레어 수선]: 예외 안전 구동 레이어 도입
            try:
                response = chat.send_message(system_instruction + "\n\n사용자 질문: " + prompt)
                return response.text
            except Exception as accessor_error:
                # SDK가 자동 도구 응답을 받아오지 못하고 raw function_calls 개체만 남겨둔 상태에서 멈춘 경우
                if 'response' in locals() and hasattr(response, 'function_calls') and response.function_calls:
                    for call in response.function_calls:
                        if call.name == "update_dashboard_parameter":
                            args = dict(call.args)
                            # 함수 강제 수동 구동 진행
                            result_str = update_dashboard_parameter(**args)
                            
                            # 가드레일: 버전을 타지 않는 안정적인 유저 인터랙션 피드백 turn 수동 구동
                            fallback_prompt = f"[시스템 인프라 가드] 도구 {call.name} 원격 실행 결과: {result_str}\n사용자의 목적을 충족하기 위한 설정 변경 예약이 완료되었습니다. 변경 사항을 요약하고, 대시보드가 자동으로 수립될 것임을 사용자에게 친절하게 브리핑하십시오."
                            response = chat.send_message(fallback_prompt)
                    return response.text
                else:
                    # function_calls 조차 없는 일반 오류는 마스킹하지 않고 통과
                    raise accessor_error
                    
        except Exception as e:
            last_error = str(e)
            err_low = last_error.lower()
            if any(msg in err_low for msg in ["api_key", "api key", "unauthorized", "quota", "exhausted", "403", "401"]):
                continue
            else:
                return f"❌ AI 상담방 내부 구동 오류가 발생했습니다: {last_error}"
                
    return f"❌ AI 가동 실패: 가용한 모든 API 키가 만료되었거나 할당량이 완전히 차단되었습니다. (최종 에러 정보: {last_error})"
