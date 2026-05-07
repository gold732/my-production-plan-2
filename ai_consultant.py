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
            
            # 안전한 텍스트 추출 로직 (분석용)
            if response and response.candidates:
                raw_text = response.candidates[0].content.parts[0].text.strip()
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
            # 자동 함수 호출 활성화
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
                
                # [🚨 에러 수정 핵심]: response.text 직접 접근 전 유효성 검사
                if response and hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    # 텍스트 파트가 존재하는지 확인
                    parts = [p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text]
                    if parts:
                        return "".join(parts)
                
                # 텍스트 응답이 없지만 함수 호출이 일어난 경우에 대한 예외 처리
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 요청하신 목적에 맞춰 시스템 파라미터를 조정했습니다. 새로운 계획을 확인해 주십시오."
                
                return "분석 결과를 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

            except Exception as accessor_error:
                # 텍스트 접근 실패 시 세션 업데이트 상태 확인 후 수동 응답
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 시스템 파라미터를 성공적으로 업데이트했습니다. 대시보드를 새로고침합니다."
                
                # 마지막 수단: 함수 호출 파트가 있는지 직접 순회
                if 'response' in locals() and hasattr(response, 'candidates'):
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'function_call'):
                            return "⚙️ 파라미터 조정 도구를 실행했습니다. 최적화 결과를 다시 생성합니다."
                
                raise accessor_error
        except Exception as e:
            # API 키 오류 등은 건너뛰고 다음 키 시도
            if any(msg in str(e).lower() for msg in ["api_key", "quota", "429", "401"]):
                continue
            return f"❌ AI 구동 오류: {str(e)}"
                
    return "❌ AI 가동 실패: 사용 가능한 모든 API 키에서 오류가 발생했습니다."
