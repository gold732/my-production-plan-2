import streamlit as st
import google.generativeai as genai
import random
import json

def get_ai_analysis(context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    last_error = "등록된 API 키가 없습니다."
    for key in available_keys:
        genai.configure(api_key=key)
        for model_name in ['gemini-2.5-flash-lite', 'gemini-2.5-flash']:
            try:
                model = genai.GenerativeModel(model_name)
                
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
    S&OP 전문가 AI 컨설턴트: 사용자의 요청을 분석하고 전략적 조언을 제공합니다.
    시나리오 이력이 포함된 컨텍스트를 분석하여 비교 기능을 수행합니다.
    """
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: 
        return "⚠️ Secrets에 'GEMINI_KEYS'를 설정해주세요."
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 지침 강화: 시나리오 이력이 있을 경우 이를 비교 분석하도록 명시
    system_instruction = f"""당신은 S&OP 생산관리 전문가입니다.

[현재 운영 환경 및 저장된 시나리오 데이터]
{context_summary}

[전략적 가이드라인]
1. 제공된 '현재 운영 데이터'와 '저장된 시나리오 이력'을 기반으로 사용자의 질문에 답변하십시오.
2. 사용자가 여러 시나리오(예: 시나리오 1, 시나리오 2) 간의 차이점을 물으면, 각 시나리오에 저장된 비용, 가동률, 임금, 재고비, 제약 조건(최대 가동률 등)을 수치적으로 비교하여 통찰을 제시하십시오.
3. 시나리오별 파라미터 변화가 결과(비용, 재고, 부재고)에 미친 영향을 분석하고, 경영진 입장에서 최적의 시나리오가 무엇인지 논리적으로 제안하십시오."""

    last_error = "등록된 API 키가 없습니다."
    
    for key in available_keys:
        genai.configure(api_key=key)
        for model_name in ['gemini-2.5-flash-lite', 'gemini-2.5-flash']:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                chat = model.start_chat()
                response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
                
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            return part.text
                
                return "조언을 생성하는 데 성공했습니다. 대시보드 지표와 함께 검토해 보시기 바랍니다."

            except Exception as e:
                last_error = str(e)
                err_low = last_error.lower()
                if any(msg in err_low for msg in ["api_key", "quota", "exhausted", "403", "401"]):
                    continue
                else:
                    return f"❌ AI 구동 오류: {last_error}"
                
    return f"❌ AI 가동 실패 (최종 에러: {last_error})"
