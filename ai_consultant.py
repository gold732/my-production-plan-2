import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다. 
    최적해를 찾을 수 없는 상황을 해결하기 위해 이 도구를 호출하십시오.
    단, 사용자가 [고정] 체크박스를 켠 잠금 상태의 파라미터는 절대 변경할 수 없습니다.
    """
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        # 구체적인 변수명 대신 간결한 거부 메시지 반환
        return f"❌ 변경 거부: 해당 파라미터는 사용자가 [고정] 상태로 잠금해 두었습니다."
    
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터가 '{val}'로 예약되었습니다."
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패"


def get_ai_analysis(context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            
            prompt = f"""당신은 생산관리 전문가입니다. S&OP 최적화 결과를 분석하여 보고서를 작성하세요.
            데이터: {context_summary}
            **경고 지침**: 가동률 100% 도달 시 비현실적 계획임을 명시하십시오.

            {{
                "risk_level": "안전/주의/심각 중 선택",
                "bottleneck_month": "핵심 월",
                "summary": "핵심 요약 (가동률 100% 경고 포함)",
                "recommendation": "권고사항"
            }}"""
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except:
            continue
    return None


def get_ai_consultant(prompt, context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정이 필요합니다."
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
            
            system_instruction = f"""당신은 S&OP 생산관리 전문가입니다.
            현재 상태: {context_summary}
            
            **[전략적 제어 핵심 규칙]**
            1. **최적화 실패 대응**: 해가 없는 상태(Infeasible)일 때, 어떤 파라미터가 잠겨 있는지 구체적으로 나열하지 마십시오. 대신 "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다"라고 요점만 말하십시오.
            2. **자율 즉시 실행**: 해가 나오지 않으면 질문하지 말고 가능한 파라미터를 스스로 결정하여 즉시 `update_dashboard_parameter`를 실행하십시오.
            3. **간결성**: 사용자가 상황을 복잡하게 느끼지 않도록 불필요한 기술적 변명을 삼가십시오."""
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            try:
                response = chat.send_message(system_instruction + "\n\n사용자 질문: " + prompt)
                return response.text
            except Exception:
                if 'response' in locals() and hasattr(response, 'function_calls') and response.function_calls:
                    for call in response.function_calls:
                        if call.name == "update_dashboard_parameter":
                            result_str = update_dashboard_parameter(**dict(call.args))
                            if "변경 거부" in result_str:
                                return "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다. 원활한 분석을 위해 일부 '고정' 설정을 해제해 주십시오."
                            response = chat.send_message(f"결과: {result_str}. 설정을 조정했으니 다시 확인해달라고 하십시오.")
                    return response.text
                raise
        except:
            continue
                
    return "❌ AI 가동 실패"
