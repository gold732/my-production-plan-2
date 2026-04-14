import google.generativeai as genai
import streamlit as st
import random

def get_ai_consultant(prompt, context_summary):
    """Gemini API 연동 및 전문가 페르소나 적용"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ Secrets에 API 키를 설정해주세요."
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            
            system_instruction = f"""1. 당신은 생산관리 전문가입니다. 데이터 분석 결과({context_summary})를 토대로 답변하세요.
                                   2. 전문적인 용어를 사용하되, 답변은 간결하고 명확해야 합니다.
                                   3. 관련 없는 질문은 "서비스 범위를 벗어난 질문입니다"라고 답하세요."""
            
            response = model.generate_content(system_instruction + "\n\n사용자 질문: " + prompt)
            return response.text
        except Exception:
            continue 
    return "❌ AI 서비스 연결에 실패했습니다."

def get_risk_analysis(utils, enable_sub):
    """가동률 데이터를 기반으로 리스크 자동 진단"""
    u_str = ", ".join([f"{i+1}월:{v:.1f}%" for i, v in enumerate(utils)])
    ctx = f"월별 가동률: [{u_str}], 외주허용여부: {enable_sub}"
    prompt = "현재 생산 가동률 데이터를 분석하여 잠재적인 병목 리스크나 유휴 인력 문제를 짧게 진단해줘."
    return get_ai_consultant(prompt, ctx)
