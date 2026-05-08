import streamlit as st
import google.generativeai as genai
import random
import json

def get_ai_analysis(context_summary):
    """Lite 모델 실패 시 Flash로 자동 전환되는 분석 엔진"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # 순차적으로 시도할 모델 리스트
    models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash']
    
    for key in available_keys:
        genai.configure(api_key=key)
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                prompt = f"""당신은 생산관리 전문가입니다. 결과 데이터를 분석하여 보고서를 JSON으로 작성하세요.
                데이터: {context_summary}
                반환 형식: {{ "risk_level": "...", "bottleneck_month": "...", "summary": "...", "recommendation": "..." }}"""
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                return json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            except:
                continue # 현재 모델 실패 시 다음 모델(Flash) 시도
    return None

def get_ai_consultant(prompt, context_summary):
    """S&OP 전략 어드바이저 (도구 없이 상담만 수행)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정 누락"
    
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            chat = model.start_chat()
            response = chat.send_message(f"상황: {context_summary}\n질문: {prompt}")
            return response.text
        except:
            continue
    return "❌ 서비스 이용 불가"
