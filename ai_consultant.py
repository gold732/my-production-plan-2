import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다. 
    단, 사용자가 [고정] 체크박스를 켠 잠금 상태의 파라미터는 절대 변경할 수 없습니다.
    """
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        # 구체적인 변수명을 나열하지 않고 간결하게 거부 메시지 반환
        return f"❌ 변경 거부: 해당 파라미터는 사용자가 [고정] 상태로 잠금해 두어 수정이 불가능합니다."
    
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터를 '{val}'로 예약 변경했습니다."
    except Exception as e:
        return f"❌ 오류: 값 타입 변환 실패"


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
            
            prompt = f"""당신은 생산관리 전문가입니다. 결과를 분석하여 JSON 보고서를 작성하세요.
            데이터: {context_summary}
            **경고**: 가동률 100%는 비현실적임을 반드시 명시하십시오."""
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            
            # response.text 접근 전 안전 검사
            if response and hasattr(response, 'candidates') and response.candidates:
                raw_text = response.candidates[0].content.parts[0].text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
        except Exception as e:
            last_error = str(e).lower()
            if any(msg in last_error for msg in ["403", "denied", "api_key", "quota", "429", "unauthorized"]):
                continue
            return {"risk_level": "🚨 시스템 오류", "bottleneck_month": "연산 중단", "summary": f"오류: {last_error}", "recommendation": "관리자 확인 필요"}
    return None


def get_ai_consultant(prompt, context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키를 설정해주세요."
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
            
            system_instruction = f"""당신은 S&OP 생산관리 전문가입니다.
            현재 상태: {context_summary}
            
            **[핵심 지침]**
            1. **최적화 실패 대응**: 해가 없는 상태라면, 파라미터가 잠겨 있다는 변명을 구체적으로 늘어놓지 마십시오. 대신 "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다"라고 요점만 말하십시오.
            2. **자율 즉시 실행**: 해가 나오지 않으면 질문하지 말고 가능한 파라미터를 스스로 결정하여 즉시 `update_dashboard_parameter`를 실행하십시오.
            3. **텍스트 미반환 방지**: 도구를 호출할 때도 사용자에게 "조정 중입니다"라는 짧은 메시지를 함께 남기도록 하십시오."""
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            try:
                response = chat.send_message(system_instruction + "\n\n사용자 질문: " + prompt)
                
                # [🚨 에러 수정]: response.text 직접 접근 전 파트 유효성 검사
                if response and hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content.parts:
                        parts = [p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text]
                        if parts: return "".join(parts)
                
                # 텍스트는 없지만 도구 실행이 성공한 경우의 피드백
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 요청하신 운영 목적에 맞춰 시스템 파라미터를 조정했습니다. 새로운 계획을 확인하십시오."
                
                return "조언을 생성하는 중에 문제가 발생했습니다. 다시 시도해주세요."

            except Exception as accessor_error:
                # 403 에러나 권한 에러 발생 시 다음 키로 로테이션
                err_low = str(accessor_error).lower()
                if any(m in err_low for m in ["403", "denied", "access", "permission"]):
                    continue
                
                # 도구 실행 중 발생한 에러 처리
                if 'response' in locals() and hasattr(response, 'function_calls') and response.function_calls:
                    for call in response.function_calls:
                        if call.name == "update_dashboard_parameter":
                            result_str = update_dashboard_parameter(**dict(call.args))
                            if "변경 거부" in result_str:
                                return "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다. 일부 고정 설정을 해제해 주십시오."
                            response = chat.send_message(f"도구 결과: {result_str}\n변경 내용을 요약해서 브리핑하십시오.")
                    return response.text
                raise accessor_error
                
        except Exception as e:
            last_error = str(e).lower()
            if any(msg in last_error for msg in ["403", "denied", "api_key", "quota", "429", "unauthorized"]):
                continue
            return f"❌ AI 구동 오류: {last_error}"
                
    return f"❌ AI 가동 실패 (모든 API 키 권한 확인 필요)"
