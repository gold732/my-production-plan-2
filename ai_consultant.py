import streamlit as st
import google.generativeai as genai
import random
import json

def get_ai_analysis(context_summary):
    """[업데이트] Lite 모델 실패 시 Flash 모델로 자동 폴백되는 무중단 진단 엔진"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 시도할 모델 우선순위 정의 (Lite -> Full)
    model_priority = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            
            # 모델 리스트를 순회하며 성공할 때까지 시도
            for model_name in model_priority:
                try:
                    model = genai.GenerativeModel(model_name)
                    
                    prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 정밀하게 분석하여 경영진을 위한 종합 진단 보고서를 JSON 형태로 작성하세요.
                    데이터: {context_summary}
                    **경고 지침**: 특정 월의 가동률이 100%에 도달하면 이는 비현실적인 가동 계획(Burnout 리스크)임을 리포트에 반드시 명시하십시오.

                    반환 형식은 반드시 아래의 JSON 스키마 구조를 100% 준수해야 합니다:
                    {{
                        "risk_level": "🟢 안전", "🟡 주의", "🚨 심각" 중 선택,
                        "bottleneck_month": "핵심 월 (예: '3월', 없으면 '없음')",
                        "summary": "최적화 결과에 대한 핵심 요약 (2~3문장). 가동률 100% 발생 시 강력 경고 포함.",
                        "recommendation": "운영 효율성 개선 및 리스크 완화를 위한 실무적 핵심 권고사항 (1~2문장)"
                    }}"""
                    
                    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                    raw_text = response.text.strip()
                    if raw_text.startswith("```"):
                        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                    
                    # 성공 시 즉시 반환
                    return json.loads(raw_text)
                except Exception:
                    # 현재 모델 실패 시 다음 모델(Flash)로 조용히 전이
                    continue
                    
        except Exception:
            # 현재 키의 모든 모델이 실패 시 다음 키로 이동
            continue

    return {
        "risk_level": "🟡 분석 불가", "bottleneck_month": "확인 불가",
        "summary": "모든 분석 엔진(Lite/Flash) 및 API 키가 응답하지 않습니다.",
        "recommendation": "잠시 후 다시 시도하거나 시스템 관리자에게 문의하십시오."
    }

def get_ai_consultant(prompt, context_summary):
    """S&OP 전략 어드바이저 (기존 로직 보존)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정이 필요합니다."
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    system_instruction = f"""당신은 S&OP 생산전략 수석 컨설턴트입니다.
현재 시스템은 '계층적 제약 완화 알고리즘'을 통해 최적해를 자동으로 찾아내고 있습니다.

[현재 운영 현황 및 최적화 결과]
{context_summary}

[당신의 임무]
1. 사용자의 질문에 대해 현재의 가동률, 비용, 재고 데이터를 기반으로 답변하십시오.
2. 시스템 조작 없이 전략적 가이드만 제공하십시오."""

    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash')
            chat = model.start_chat()
            response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
            if response.text: return response.text
        except: continue
    return "❌ AI 컨설턴트 응답 불가"
