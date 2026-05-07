import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터(비용 설정, 공정 제약 설정, 운영 초기값 등)를 동적으로 변경합니다."""
    lock_key = f"lock_{parameter_key}"
    if st.session_state.get(lock_key, False):
        return f"❌ 변경 거부: '{parameter_key}' 파라미터는 사용자가 [고정] 상태로 잠금해 두었으므로 수정이 불가능합니다."
    
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
        
        return f"✅ 예약 성공: '{parameter_key}' 파라미터 값이 '{val}'로 대기 등록되었습니다."
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
            
            # [수정]: 100% 가동률에 대한 비현실성 지적 로직 추가
            prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 분석하여 경영진 보고서를 JSON으로 작성하세요.
            데이터: {context_summary}
            
            **[중요 분석 지침]**:
            - 가동률이 100%에 도달한 달이 있다면, 이는 설비 고장, 결근, 품질 이슈 등 돌발 상황에 대응할 '운영 버퍼'가 전혀 없는 매우 비현실적이고 위험한 계획임을 반드시 지적하십시오.
            - 가동률 100%는 서류상 최적일 수 있으나 실무적으로는 '🚨 심각' 또는 '🟡 주의' 단계로 간주하고, 85~92% 수준의 적정 가동률 유지를 위해 인력 확충이나 외주 검토를 권고하십시오.
            
            반환 형식(JSON):
            {{
                "risk_level": "🟢 안전", "🟡 주의", "🚨 심각" 중 선택,
                "bottleneck_month": "핵심 월 (예: '3월', 없으면 '없음')",
                "summary": "결과 요약 (2~3문장)",
                "recommendation": "개선 권고사항 (가동률 100% 이슈 포함, 1~2문장)"
            }}"""
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            last_error = str(e)
            continue
    return {"risk_level": "🟡 분석 불가", "bottleneck_month": "확인 불가", "summary": f"오류: {last_error}", "recommendation": "수동 확인 필요"}


def get_ai_consultant(prompt, context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정 필요"
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite', tools=[update_dashboard_parameter])
            system_instruction = f"""당신은 S&OP 생산관리 전문가입니다. 현재 상태: {context_summary}
            사용자가 가동률, 재고, 비용 등의 조정을 요청하면 `update_dashboard_parameter`를 사용하여 시스템을 직접 제어하십시오.
            특히 가동률이 지나치게 높다면(100%) 위험성을 경고하고 제어판의 `max_util` 등을 조정할 것을 제안하거나 직접 실행하십시오."""
            
            chat = model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(system_instruction + "\n\n사용자 질문: " + prompt)
            return response.text
        except Exception as e:
            continue
    return "❌ AI 가동 실패"
