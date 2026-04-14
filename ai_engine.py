import google.generativeai as genai
import streamlit as st
import random

def get_ai_consultant(prompt, context_summary, mode="consult"):
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키를 설정해주세요."
    
    genai.configure(api_key=random.choice(list(keys)))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    # 모드에 따른 시스템 지시문 분리
    if mode == "demand":
        system_instruction = "당신은 수요 예측기입니다. 설명 없이 오직 보정된 숫자 6개(쉼표 구분)만 출력하세요. 다른 말은 절대 하지 마세요."
    else:
        system_instruction = f"""당신은 생산관리 전문가입니다. 데이터({context_summary})를 기반으로 
                                전략적이고 풍부한 분석 보고서를 작성하세요. 전문 용어를 사용하고 
                                인사이트가 담긴 제언을 포함하세요."""
    
    try:
        response = model.generate_content(system_instruction + "\n\n사용자 요청: " + prompt)
        return response.text
    except:
        return "❌ AI 연결 오류"

def get_risk_analysis(utils, enable_sub):
    u_str = ", ".join([f"{i+1}월:{v:.1f}%" for i, v in enumerate(utils)])
    ctx = f"가동률:[{u_str}], 외주:{enable_sub}"
    return get_ai_consultant("현재 가동률의 위험 요소를 분석하고 구체적인 대응책을 제시해줘.", ctx, mode="consult")
