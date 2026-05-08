import streamlit as st
import google.generativeai as genai
import random
import json

def get_ai_analysis(context_summary):
    """최적화 결과에 대한 자동 진단 보고서 생성 (기존 로직 보존)"""
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return None
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash-lite')
            
            prompt = f"""당신은 생산관리 전문가입니다. 제공된 S&OP 최적화 결과 데이터를 분석하여 보고서를 JSON으로 작성하세요.
            데이터: {context_summary}
            반환 형식: {{ "risk_level": "...", "bottleneck_month": "...", "summary": "...", "recommendation": "..." }}"""
            
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except: continue
    return None

def get_ai_consultant(prompt, context_summary):
    """
    [개편] S&OP 전략 어드바이저:
    이제 파라미터를 직접 수정하지 않고, 시스템이 계산한 결과를 바탕으로 
    경영적 의사결정을 돕는 분석 보고서를 제공합니다.
    """
    keys = st.secrets.get("GEMINI_KEYS", [])
    if not keys: return "⚠️ API 키 설정이 필요합니다."
    
    available_keys = list(keys)
    random.shuffle(available_keys)
    
    # AI에게 부여하는 새로운 역할 (분석가 중심)
    system_instruction = f"""당신은 S&OP 생산전략 수석 컨설턴트입니다.
현재 시스템은 '계층적 제약 완화 알고리즘'을 통해 최적해를 자동으로 찾아내고 있습니다.

[현재 운영 현황 및 최적화 결과]
{context_summary}

[당신의 임무]
1. 사용자의 질문에 대해 현재의 최적화 데이터(가동률, 비용, 재고)를 기반으로 답변하십시오.
2. 만약 시스템이 '제약 완화(예: 가동률 상향, 외주 허용)'를 통해 해를 찾았다면, 그로 인한 리스크와 향후 대안을 설명하십시오.
3. 파라미터 수정 권고는 말로 전달하되, 직접 시스템을 조작하려 하지 마십시오. (사용자가 직접 사이드바에서 조정하도록 유도)"""

    for key in available_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name='gemini-2.5-flash')
            
            # 단순 텍스트 기반 상담으로 전환 (Tool 제거)
            chat = model.start_chat()
            response = chat.send_message(f"{system_instruction}\n\n사용자 질문: {prompt}")
            
            if response.text:
                return response.text
        except Exception as e:
            continue
                
    return "❌ AI 컨설턴트 서비스 일시 중단 (API 오류)"
