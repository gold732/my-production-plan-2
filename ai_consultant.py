import streamlit as st
import google.generativeai as genai
import random
import json

def get_ai_analysis(context_summary):
    """Lite 모델 우선 시도 후 Flash 모델로 자동 폴백"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    
    for key in available_keys:
        genai.configure(api_key=key)
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                prompt = f"""생산관리 전문가로서 결과 데이터를 정밀 분석하여 JSON 보고서를 작성하세요.
                데이터: {context_summary}
                - 가동률 100% 발생 시 위험(Burnout) 경고 포함.
                형식: {{ "risk_level": "...", "bottleneck_month": "...", "summary": "...", "recommendation": "..." }}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                return json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            except: continue
    return {"risk_level": "🟡 분석 지연", "summary": "엔진 응답 없음", "recommendation": "지표 직접 확인"}

def get_ai_consultant(prompt, context_summary):
    """S&OP 전략 어드바이저"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정 누락"
    
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            chat = model.start_chat()
            response = chat.send_message(f"상황: {context_summary}\n질문: {prompt}")
            return response.text
        except: continue
    return "❌ 서비스 이용 불가"
