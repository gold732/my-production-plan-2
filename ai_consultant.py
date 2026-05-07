import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다."""
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
    except Exception:
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
            prompt = f"분석 보고서 작성 데이터: {context_summary}"
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            
            if response and hasattr(response, 'candidates') and response.candidates:
                raw_text = response.candidates[0].content.parts[0].text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                return json.loads(raw_text)
        except Exception as e:
            # 403이나 접근 거부 에러 시 조용히 다음 키로 스킵
            err_msg = str(e).lower()
            if any(m in err_msg for m in ["403", "denied", "api_key", "quota", "429", "unauthorized"]):
                continue
    return None

def get_ai_consultant(prompt, context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정이 필요합니다." [cite: 2]
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
            
            system_instruction = f"""당신은 S&OP 생산관리 전문가입니다. 
            현재 상태: {context_summary}
            1. 최적화 실패 시 구체적 변수 나열 금지. "현재 고정되지 않은 값만 조절한다고 최적해는 안 나옵니다"라고만 답변할 것.
            2. 해가 없으면 즉시 update_dashboard_parameter를 실행할 것.
            """
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            try:
                response = chat.send_message(system_instruction + "\n\n질문: " + prompt)
                
                # 안전한 응답 텍스트 추출 (403 등으로 인한 candidate 누락 방어)
                if response and hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content.parts:
                        parts = [p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text]
                        if parts: return "".join(parts)
                
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 요청하신 목적에 맞춰 시스템 파라미터를 조정했습니다. 새로운 계획을 확인해 주십시오."
                
                continue # 텍스트가 없으면 다음 키 시도
                
            except Exception as accessor_error:
                err_msg = str(accessor_error).lower()
                # 접근 거부 등 발생 시 다음 키로 로테이션
                if any(m in err_msg for m in ["403", "denied", "access", "permission"]):
                    continue
                if st.session_state.get('param_updated_by_ai'):
                    return "✅ 시스템 설정을 업데이트했습니다. 다시 연산합니다."
                raise accessor_error
                
        except Exception as e:
            err_msg = str(e).lower()
            if any(m in err_msg for m in ["403", "denied", "api_key", "quota", "429", "unauthorized"]):
                continue
            return f"❌ 시스템 연결 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                
    return "❌ 현재 사용 가능한 분석 엔진이 모두 만료되었습니다. API 키 상태를 확인해주세요."
