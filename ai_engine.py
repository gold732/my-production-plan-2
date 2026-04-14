import google.generativeai as genai
import streamlit as st
import random

def get_ai_consultant(prompt, context_summary):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키를 설정해주세요."
    
    genai.configure(api_key=random.choice(list(keys)))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    # 지시사항: 아주 짧게 대답할 것
    system_instruction = f"""1. 당신은 생산관리 전문가입니다. 데이터: {context_summary}
                             2. 모든 답변은 2문장 이내로 핵심 수치만 답하세요.
                             3. 서론, 인사말, 부연 설명은 절대 금지합니다."""
    
    try:
        response = model.generate_content(system_instruction + "\n\n질문: " + prompt)
        return response.text
    except:
        return "❌ AI 연결 오류"

def get_risk_analysis(utils, enable_sub):
    u_str = ", ".join([f"{i+1}월:{v:.1f}%" for i, v in enumerate(utils)])
    ctx = f"가동률:[{u_str}], 외주:{enable_sub}"
    return get_ai_consultant("현재 가동률의 위험 요소를 한 문장으로 진단해줘.", ctx)
