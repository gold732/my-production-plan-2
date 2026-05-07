import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다."""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        # 구체적인 리스트 나열 없이 간결하게 거부
        return f"❌ 변경 거부: 현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다."
    
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터 값이 '{val}'로 예약되었습니다."
    except Exception:
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
            
            prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 정밀하게 분석하여 경영진을 위한 종합 진단 보고서를 JSON 형태로 작성하세요.
            데이터: {context_summary}
            **경고 지침**: 가동률 100% 도달 시 비현실적 계획임을 리포트에 반드시 명시하십시오."""
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            
            # 안전한 텍스트 추출 로직
            if response and hasattr(response, 'candidates') and response.candidates:
                raw_text = response.candidates[0].content.parts[0].text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
        except Exception as e:
            last_error = str(e).lower()
            if any(msg in last_error for msg in ["403", "denied", "api_key", "quota", "429", "unauthorized"]):
                continue
    return None


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
            
            system_instruction = f"""당신은 S&OP 생산관리 전문가입니다.
            현재 상태: {context_summary}
            
            **[전략적 제어 핵심 규칙]**
            1. **최적화 실패 대응**: 해가 없는 상태(Infeasible)라면 어떤 변수가 잠겨 있는지 변명하지 마십시오. 대신 "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다"라고만 말하십시오.
            2. **자율 즉시 실행**: 해가 나오지 않으면 질문 없이 즉시 update_dashboard_parameter 도구를 호출하여 해를 찾으십시오.
            3. **거짓말 금지**: 일부 파라미터가 고정되었다고 해서 "모든 파라미터가 고정되었다"고 과장하지 마십시오.
            """
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            try:
                response = chat.send_message(system_instruction + "\n\n사용자 질문: " + prompt)
                
                # [🚨 에러 수정 핵심]: response.text 직접 접근 전 파트 유효성 검사
                if response and hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content.parts:
                        parts = [p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text]
                        if parts: return "".join(parts)
                
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 요청하신 목적에 맞춰 시스템 파라미터를 조정했습니다. 새로운 계획을 확인하십시오."
                
                continue # 텍스트가 없으면 다음 키 시도
                
            except Exception as accessor_error:
                err_msg = str(accessor_error).lower()
                # 403 권한 에러 시 즉시 다음 키로 전환
                if any(m in err_msg for m in ["403", "denied", "access", "permission"]):
                    continue
                
                # 도구 실행 중 거부 메시지 처리
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 시스템 파라미터를 성공적으로 업데이트했습니다. 최적화 연산을 다시 수행합니다."
                
                return "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다. 일부 고정 설정을 해제해 주십시오."
                
        except Exception as e:
            last_error = str(e).lower()
            if any(msg in last_error for msg in ["403", "denied", "api_key", "quota", "429", "unauthorized"]):
                continue
            return f"❌ AI 구동 오류: {last_error}"
                
    return f"❌ AI 가동 실패: 사용 가능한 모든 API 엔진이 응답하지 않거나 권한이 없습니다."
