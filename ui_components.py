import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def render_sidebar():
    """모든 파라미터와 AI 모델 선택 기능이 포함된 사이드바"""
    with st.sidebar:
        st.header("🎮 시스템 제어판")
        
        # [추가] AI 모델 선택 UI
        st.subheader("🤖 AI 엔진 설정")
        st.radio("분석 모델 선택", ["gemini-2.5-flash", "gemini-2.5-flash-lite"], 
                 key="ai_model", help="Quota 상황에 맞춰 모델을 변경하세요. Flash는 정교한 제어가, Lite는 빠른 분석이 특징입니다.")
        
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1: opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"], key="opt_mode")
        with c2: st.checkbox("고정", key="lock_opt_mode")

        st.markdown("---")
        st.subheader("🏭 공급망 전략")
        c1, c2 = st.columns([3, 1])
        with c1: enable_sub = st.toggle("외주 하청 허용", key="enable_sub")
        with c2: st.checkbox("고정", key="lock_enable_sub")

        st.markdown("---")
        st.subheader("⏱️ 공정 효율 및 제약")
        c1, c2 = st.columns([3, 1])
        with c1: std_time = st.number_input("제품당 표준 작업 시간 (Hr)", min_value=1.0, step=0.1, key="std_time")
        with c2: st.checkbox("고정", key="lock_std_time")
        c1, c2 = st.columns([3, 1])
        with c1: working_days = st.slider("월간 가동 일수", 1, 30, key="working_days")
        with c2: st.checkbox("고정", key="lock_working_days")
        c1, c2 = st.columns([3, 1])
        with c1: ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 100, key="ot_limit")
        with c2: st.checkbox("고정", key="lock_ot_limit")

        st.markdown("---")
        st.subheader("🛡️ 운영 안전 가드")
        c1, c2 = st.columns([3, 1])
        with c1: max_util = st.number_input("최대 허용 가동률 (%)", min_value=1.0, max_value=100.0, step=0.5, key="max_util")
        with c2: st.checkbox("고정", key="lock_max_util")
        c1, c2 = st.columns([3, 1])
        with c1: min_inv = st.number_input("최소 유지 재고량 (ea)", min_value=0, key="min_inv")
        with c2: st.checkbox("고정", key="lock_min_inv")
        c1, c2 = st.columns([3, 1])
        with c1: max_cost = st.number_input("최대 허용 총 비용 (천원)", min_value=0.0, key="max_cost")
        with c2: st.checkbox("고정", key="lock_max_cost")

        st.markdown("---")
        st.subheader("💰 운영 비용 설정")
        costs = [("v_c_reg", "정규 임금"), ("v_c_ot", "초과 수당"), ("v_c_h", "고용비"), ("v_c_l", "해고비"),
                 ("v_c_inv", "재고비"), ("v_c_back", "부재고비"), ("v_c_mat", "재료비"), ("v_c_sub", "외주비")]
        for k, lbl in costs:
            c1, c2 = st.columns([3, 1])
            with c1: st.number_input(lbl, key=k)
            with c2: st.checkbox("고정", key=f"lock_{k}")

        st.markdown("---")
        st.subheader("📈 초기값 및 수요")
        c1, c2 = st.columns([3, 1])
        with c1: demand_raw = st.text_input("수요 예측 (쉼표 구분)", key="demand_raw")
        with c2: st.checkbox("고정", key="lock_demand_raw")
        demand = [float(d.strip()) for d in demand_raw.split(",") if d.strip()]
        inits = [("v_w_init", "현재 근로자"), ("v_i_init", "현재고"), ("v_i_final", "목표재고")]
        for k, lbl in inits:
            c1, c2 = st.columns([3, 1])
            with c1: st.number_input(lbl, key=k)
            with c2: st.checkbox("고정", key=f"lock_{k}")
            
    return demand, enable_sub, std_time, working_days, ot_limit

def render_supply_demand_tab(m, utils, demand):
    """1번 탭: AI 진단 보고서와 고해상도 공급망 차트"""
    if st.session_state.get('ai_analysis'):
        analysis = st.session_state['ai_analysis']
        st.markdown("### 🤖 AI 전문 컨설턴트 종합 진단 보고서")
        c_m1, c_m2 = st.columns([1, 4])
        with c_m1:
            st.metric("운영 리스크 등급", analysis.get("risk_level", "🟡 주의"))
            st.metric("최대 병목 월", analysis.get("bottleneck_month", "없음"))
        with c_m2:
            st.info(f"**📋 핵심 요약:** {analysis.get('summary', '')}")
            st.warning(f"**💡 권고사항:** {analysis.get('recommendation', '')}")
        st.markdown("---")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
    avg_u = sum(utils)/len(utils)
    k2.metric("평균 가동률", f"{avg_u:.1f}%")
    k3.metric("인력 변동", f"+{sum(m.H[t]() for t in range(1,len(demand)+1)):.0f} / -{sum(m.L[t]() for t in range(1,len(demand)+1)):.0f}명")
    k4.metric("총 부재고", f"{sum(m.S[t]() for t in range(1,len(demand)+1)):,.0f}ea")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.P[t]() for t in range(1,len(demand)+1)], name="자체 생산", marker_color='royalblue'))
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.C[t]() for t in range(1,len(demand)+1)], name="외주 하청", marker_color='lightslategray'))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=demand, name="예상 수요", line=dict(color='darkorange', dash='dash')))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=[m.I[t]() for t in range(1,len(demand)+1)], name="재고 수준", yaxis="y2", line=dict(color='green')))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack')
    st.plotly_chart(fig, use_container_width=True)

def render_risk_efficiency_tab(m, utils, demand):
    """2번 탭: 리스크 진단"""
    st.subheader("📉 리스크 및 효율 진단")
    c1, c2 = st.columns(2)
    with c1:
        costs = { "노무비": sum(st.session_state['v_c_reg']*m.W[t]() for t in range(1,len(demand)+1)),
                  "재고비": sum(st.session_state['v_c_inv']*m.I[t]() for t in range(1,len(demand)+1)),
                  "외주비": sum(st.session_state['v_c_sub']*m.C[t]() for t in range(1,len(demand)+1)) }
        st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)
    with c2:
        st.plotly_chart(px.area(x=[f"{t}월" for t in range(1,len(demand)+1)], y=utils, title="가동률 추이"), use_container_width=True)

def render_data_master_tab(m, utils, demand):
    """3번 탭: 정밀 데이터"""
    ds = []
    for t in range(1, len(demand) + 1):
        ds.append({ "월": f"{t}월", "생산": m.P[t](), "외주": m.C[t](), "재고": m.I[t](), "가동률": f"{utils[t-1]:.1f}%" })
    st.dataframe(pd.DataFrame(ds).set_index("월"), use_container_width=True)
