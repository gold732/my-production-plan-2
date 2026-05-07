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
    """
    S&OP 전문가 AI 컨설턴트: 
    사용자의 요청을 분석하고, 필요시 대시보드 파라미터를 직접 수정합니다.
    """
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: 
        return "⚠️ Secrets에 'GEMINI_KEYS'를 설정해주세요."
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 1. 현재 대시보드의 잠금(Lock) 상태를 동적으로 파악
    # 주의: 대시보드의 체크박스 키값(lock_...)과 일치해야 합니다.
    target_params = [
        'std_time', 'working_days', 'ot_limit', 'max_util', 
        'min_inv', 'max_cost', 'enable_sub', 'opt_mode'
    ]
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    # 2. AI에게 부여할 강력한 시스템 지침 (잠금 상태 포함)
    system_instruction = f"""당신은 S&OP 생산관리 전문가이자 제어판을 완벽하게 통제하는 컨트롤 에이전트입니다.

[현재 운영 환경 데이터]
{context_summary}

[파라미터 잠금(Lock) 현황]
{lock_status}
※ 중요: 'True'인 항목은 사용자가 고정한 것이므로 절대 수정할 수 없습니다. 
반드시 'False'인 항목들만 조절하여 최적의 운영 방안을 찾으십시오.

[전략적 제어 규칙]
1. **논리적 우회 탐색**: 예산(max_cost)이나 가동률(max_util)이 고정되어 수정할 수 없다면, 즉시 'working_days'(가동일)를 늘리거나 'ot_limit'(연장근로)을 조정하는 등 '변경 가능한(False)' 변수들을 조합하여 문제를 해결하십시오.
2. **최적화 실패(Infeasible) 대응**: 현재 상태가 실패라면, 질문하지 말고 즉시 `update_dashboard_parameter`를 실행하여 가능한 범위 내에서 해를 찾으십시오.
3. **변명 금지**: "수정이 불가능합니다"라고 말하기 전에, 잠기지 않은 다른 변수가 있는지 샅샅이 검토하십시오.
4. **결과 브리핑**: 파라미터를 수정한 후에는 어떤 값을 왜 바꿨는지, 그 결과가 어떻게 개선되었는지 논리적으로 설명하십시오."""

    last_error = "등록된 API 키가 없습니다."
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            # 모델 설정 (함수 도구 포함)
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash', # 혹은 사용 중인 최신 모델명
                tools=[update_dashboard_parameter]
            )
            
            # 자동 함수 호출 활성화
            chat = model.start_chat(enable_automatic_function_calling=True)
            
            # 메시지 전송 (지침 + 사용자 질문)
            response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
            
            # [에러 방지] response.text에 직접 접근하기 전, 유효한 텍스트 파트가 있는지 확인
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        return part.text
            
            return "✅ 파라미터 조정을 완료했습니다. 대시보드에서 업데이트된 결과를 확인하세요."

        except Exception as e:
            last_error = str(e)
            # API 키 이슈(쿼터 초과 등)인 경우 다음 키로 시도
            if any(msg in last_error.lower() for msg in ["api_key", "quota", "exhausted", "403", "401"]):
                continue
            else:
                return f"❌ AI 구동 오류: {last_error}"
                
    return f"❌ AI 가동 실패 (최종 에러: {last_error})"
