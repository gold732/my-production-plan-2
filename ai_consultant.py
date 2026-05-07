import streamlit as st
import google.generativeai as genai
import random
import json

def update_dashboard_parameter(parameter_key: str, new_value: str) -> str:
    """대시보드의 제어판 입력 파라미터를 동적으로 변경합니다."""
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


def get_ai_analysis(context_summary, model_name='gemini-2.5-flash-lite'):
    """전달받은 모델명을 사용하여 경영진 리포트를 생성합니다."""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            
            prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 정밀하게 분석하여 경영진을 위한 종합 진단 보고서를 JSON 형태로 작성하세요.
            데이터: {context_summary}
            **경고 지침**: 특정 월의 가동률이 100%에 도달하면 이는 비현실적인 가동 계획(Burnout 리스크)임을 리포트에 반드시 명시하십시오.

            반환 형식은 반드시 아래의 JSON 스키마 구조를 100% 준수해야 합니다:
            {{
                "risk_level": "🟢 안전", "🟡 주의", "🚨 심각" 중 하나 선택,
                "bottleneck_month": "가동률 과부하 월 명시",
                "summary": "핵심 요약 브리핑 문구 (2~3문장)",
                "recommendation": "리스크 완화를 위한 권고사항"
            }}"""
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            last_error = str(e)
            if any(msg in last_error.lower() for msg in ["api_key", "quota", "exhausted", "403", "401"]):
                continue
            else:
                return {"risk_level": "🚨 시스템 오류", "bottleneck_month": "연산 중단", "summary": f"오류: {last_error}", "recommendation": "관리자 확인 요청"}
    return {"risk_level": "🟡 분석 불가", "bottleneck_month": "확인 불가", "summary": f"Quota 소진: {last_error}", "recommendation": "수동 확인 요망"}


def get_ai_consultant(prompt, context_summary, model_name='gemini-2.5-flash'):
    """전달받은 모델명을 사용하여 파라미터 제어 및 상담을 수행합니다."""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets 설정 확인 필요"
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    target_params = ['std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost', 'enable_sub', 'opt_mode']
    lock_status = {p: st.session_state.get(f"lock_{p}", False) for p in target_params}
    
    system_instruction = f"""당신은 S&OP 전문가 컨트롤 에이전트입니다.
    [운영 데이터] {context_summary}
    [잠금 현황] {lock_status} (True 항목 수정 불가)
    변경 가능한(False) 변수들을 조합하여 문제를 해결하고, 수정 후 논리적 근거를 설명하십시오."""

    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name=model_name, tools=[update_dashboard_parameter])
            chat = model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text: return part.text
            return "✅ 작업 완료. 결과를 대시보드에서 확인하세요."
        except Exception as e:
            last_error = str(e)
            if any(msg in last_error.lower() for msg in ["api_key", "quota", "exhausted", "403", "401"]): continue
            else: return f"❌ AI 구동 오류: {last_error}"
    return f"❌ AI 가동 실패: {last_error}"
