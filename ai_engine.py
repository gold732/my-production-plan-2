import google.generativeai as genai
import streamlit as st
import random

def get_ai_response(prompt, context):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정 필요"
    
    genai.configure(api_key=random.choice(keys))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    instruction = f"당신은 S&OP 전문가입니다. 다음 데이터를 참고하여 답변하세요: {context}"
    response = model.generate_content(instruction + "\n\n질문: " + prompt)
    return response.text

def get_risk_analysis(utils):
    ctx = f"월별 가동률: {utils}"
    prompt = "현재 가동률을 보고 생산 병목 리스크를 1문장으로 진단해줘."
    return get_ai_response(prompt, ctx)
