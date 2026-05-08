import streamlit as st
import google.generativeai as genai
import random
import json

def get_ai_analysis(context_summary):
    """[복구] 원본의 상세 분석 지침을 유지하며 Lite -> Flash 자동 전환 적용"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 순차 시도 모델
    models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            for model_name in models:
                try:
                    model = genai.GenerativeModel(model_name)
                    # [원본 프롬프트 100% 복구]
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
                except:
                    continue # 모델 실패 시 다음 모델 시도
        except:
            continue
    return None

def get_ai_consultant(prompt, context_summary):
    """[복구] 원본 전문가 상담 지침 유지 (파라미터 제어 도구만 제거)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정이 필요합니다."
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 원본 시스템 지침 복구
    system_instruction = f"""당신은 S&OP 생산관리 전문가이자 경영 컨설턴트입니다. 
    현재 대시보드 데이터를 바탕으로 사용자의 전략적 의사결정을 지원하십시오.
    
    [현재 운영 데이터]
    {context_summary}
    
    ※ 참고: 파라미터 수정이 필요하다고 판단되면 사용자에게 사이드바에서 직접 값을 조정하도록 논리적으로 권고하십시오."""

    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            chat = model.start_chat()
            response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
            return response.text
        except:
            continue
    return "❌ 서비스 응답 불가"
