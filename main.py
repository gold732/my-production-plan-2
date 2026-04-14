import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyomo.environ import *

# 사용자 정의 모듈 임포트
from optimization import solve_production_plan
from ai_engine import get_ai_consultant, get_risk_analysis

# 1. 페이지 설정
st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("🚜 원예장비 AI 총괄생산계획 시스템")

# 2. 세션 상태 초기화 (계산 결과 및 대화 기록 보존)
if 'messages' not in st.session_state: 
    st.session_state.messages = []
if 'res' not in st.session_state: 
    st.session_state.res = None
if 'utils' not in st.session_state:
    st.session_state.utils = []

# --- 3. 사이드바 영역 (기존 모든 기능 및 제약 설정) ---
with st.sidebar:
    st.header("🎮 시스템 제어판")
    opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"])
    domain_type = NonNegativeIntegers if "IP" in opt_mode else NonNegativeReals
    
    st.markdown("---")
    st.subheader("🏭 공급망 전략")
    enable_sub = st.toggle("외주 하청(Outsourcing) 허용", value=True)

    st.markdown("---")
    st.subheader("🔮 AI 수요 시나리오")
    trend = st.selectbox("시장 트렌드 선택", ["평시", "호황(원예 붐)", "불황", "봄철 수요 폭증"])
    demand_raw = st.text_input("6개월 수요 예측 (쉼표 구분)", "1600, 3000, 3200, 3800, 2200, 2200")
    
    if st.button("🪄 AI에게 수요 보정 요청"):
        # ai_engine 모듈 호출 (간결한 응답)
        ai_suggestion = get_ai_consultant(f"현재 수요 {demand_raw}를 {trend} 상황에 맞춰 숫자 6개로만 보정해줘.", "수요 예측")
        st.success(f"AI 추천 시나리오: {ai_suggestion}")

    st.markdown("---")
    st.subheader("⏱️ 공정 효율 및 제약")
    std_time = st.slider("제품당 표준 작업 시간 (Hr)", 1.0, 10.0, 4.59)
    working_days = st.slider("월간 가동 일수", 1, 30, 15)
    ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 30, 10)

    st.markdown("---")
    st.subheader("💰 운영 비용 설정 (천원)")
    v_c_reg = st.number_input("정규 임금 (인/월)", value=640)
    v_c_ot = 6    # 초과 근무 수당 (Hr)
    v_c_h = 300   # 신규 고용 비용 (인)
    v_c_l = 500   # 해고 비용 (인)
    v_c_inv = 2   # 재고 유지비 (개/월)
    v_c_sub = 30  # 외주 하청 비용 (개당)
    v_c_mat = 10  # 재료비 (개당)
    v_c_back = 5  # 부재고 비용 (개/월)

    st.markdown("---")
    v_w_init = st.number_input("현재 근로자 수", value=80)
    v_i_init = 1000  # 초기 재고
    v_i_final = 500  # 기말 목표 재고

# 입력받은 수요 텍스트를 리스트로 변환
demand = [float(d.strip()) for d in demand_raw.split(",")]

# --- 4. 메인 콘텐츠 영역 (탭 구성) ---
tab1, tab2, tab3 = st.tabs(["📊 운영 대시보드", "📉 리스크 분석", "💬 AI 전략 상담방"])

with tab1:
    # 최적화 실행 버튼
    if st.button("🚀 최적 생산계획 수립 실행"):
        with st.spinner('최적화 계산 중...'):
            # optimization 모듈 호출
            m, sol = solve_production_plan(demand, domain_type, v_c_reg, v_c_ot, v_c_h, v_c_l, v_c_inv, v_c_back, v_c_mat, v_c_sub, std_time, working_days, ot_limit, v_w_init, v_i_init, v_i_final, enable_sub)
            
            if m and sol.solver.termination_condition == TerminationCondition.optimal:
                st.session_state.res = m
                # 가동률 계산 로직
                st.session_state.utils = [(m.P[t]() * std_time / (8 * working_days * m.W[t]()) * 100) if m.W[t]() > 0 else 0 for t in range(1, 7)]
                st.toast("✅ 최적화 성공!")
            else:
                st.error("❌ 최적해를 찾지 못했습니다. 제약 조건을 조정해 보세요.")

    # 결과가 존재할 경우 시각화 출력
    if st.session_state.res:
        m = st.session_state.res
        
        # 상단 핵심 지표 (KPI)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
        k2.metric("평균 가동률", f"{sum(st.session_state.utils)/6:.1f}%")
        k3.metric("인력 변동 수", f"{sum(m.H[t]() + m.L[t]() for t in range(1,7)):.0f}명")
        k4.metric("기말 재고량", f"{m.I[6]():,.0f}ea")

        # 메인 차트: 생산/수요/재고 흐름
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.P[t]() for t in range(1,7)], name="자체 생산", marker_color='royalblue'))
        fig.add_trace(go.Bar(x=list(range(1,7)), y=[m.C[t]() for t in range(1,7)], name="외주 하청", marker_color='lightslategray'))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=demand, name="예상 수요", line=dict(color='crimson', dash='dash')))
        fig.add_trace(go.Scatter(x=list(range(1,7)), y=[m.I[t]() for t in range(1,7)], name="재고 수준", yaxis="y2", line=dict(color='orange')))
        
        fig.update_layout(
            title="월별 통합 생산 및 재고 흐름",
            yaxis2=dict(overlaying='y', side='right'),
            barmode='stack',
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # 하단 상세 그래프 2종 (복구 완료)
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("💰 비용 세부 구성")
            costs_breakdown = {
                "노무비": sum(v_c_reg * m.W[t]() for t in range(1, 7)),
                "재료비": sum(v_c_mat * m.P[t]() for t in range(1, 7)),
                "외주비": sum(v_c_sub * m.C[t]() for t in range(1, 7)),
                "기타(재고/채용/해고)": m.cost() - sum((v_c_reg * m.W[t]() + v_c_mat * m.P[t]() + v_c_sub * m.C[t]()) for t in range(1, 7))
            }
            fig_pie = px.pie(names=list(costs_breakdown.keys()), values=list(costs_breakdown.values()), hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_r:
            st.subheader("👷 월별 인력 운영 현황")
            worker_trend = pd.DataFrame({
                "Month": list(range(1, 7)),
                "Workers": [m.W[t]() for t in range(1, 7)]
            })
            st.line_chart(worker_trend.set_index("Month"))

with tab2:
    if st.session_state.res:
        st.subheader("🚩 AI 생산 리스크 진단")
        # ai_engine 모듈 호출
        risk_text = get_risk_analysis(st.session_state.utils, enable_sub)
        st.warning(risk_text)
        
        # 가동률 상세 차트
        st.subheader("📈 생산 가동률 추이 (%)")
        st.line_chart(pd.DataFrame({"가동률": st.session_state.utils}, index=range(1,7)))

with tab3:
    st.subheader("💬 AI 전략 상담방")
    
    # 기능 버튼들
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🧹 대화 내용 초기화"):
            st.session_state.messages = []
            st.rerun()
    with c_btn2:
        if st.button("📄 핵심 요약 보고서 생성"):
            if st.session_state.res:
                summary_prompt = "현재 수립된 생산 계획의 핵심 성과를 경영진 보고용으로 요약해줘."
                report = get_ai_consultant(summary_prompt, f"총 비용: {st.session_state.res.cost():,.0f}k")
                st.success(f"📋 AI 요약 보고: {report}")

    st.markdown("---")
    
    # 대화 기록 출력
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("생산 계획이나 운영 전략에 대해 질문하세요."):
        # 사용자 메시지 저장
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # AI 응답 생성
        if st.session_state.res:
            ctx_info = f"총 비용: {st.session_state.res.cost():,.0f}, 외주 허용: {enable_sub}, 가동률: {st.session_state.utils}"
        else:
            ctx_info = "아직 최적화 계획이 수립되지 않았음."

        with st.chat_message("assistant"):
            ai_res = get_ai_consultant(prompt, ctx_info)
            st.markdown(ai_res)
            # AI 메시지 저장
            st.session_state.messages.append({"role": "assistant", "content": ai_res})
