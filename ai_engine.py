import google.generativeai as genai
import streamlit as st
import random

def get_ai_consultant(prompt, context_summary):
    """생산관리 전문가 페르소나를 가진 AI 상담 기능"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets에 'GEMINI_KEYS'를 설정해주세요."
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            
            system_instruction = f"""
            1. 당신은 생산관리 전문가입니다. 데이터 기반으로 답변하세요: {context_summary}
            2. 전문 용어를 사용하되 간결하게 답변하세요.
            3. 데이터 외의 질문은 거절하세요.
            """
            response = model.generate_content(system_instruction + "\n\n사용자 질문: " + prompt)
            return response.text
        except: continue 
    return "❌ AI 연결 실패"

def analyze_risks(utils):
    """가동률 데이터를 분석하여 병목 리스크 진단"""
    ctx = f"월별 가동률 추이: {utils}"
    prompt = "가동률이 95%를 넘거나 60% 미만인 달의 리스크를 분석하고 대응책을 한 문장으로 제시해줘."
    return get_ai_consultant(prompt, ctx)
