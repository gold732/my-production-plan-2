import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def render_sidebar():
    """모든 기초 파라미터 위젯 및 고정(Lock) 기능을 포함한 사이드바"""
    with st.sidebar:
        st.header("🎮 시스템 제어판")
        
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
        st.subheader("🛡️ 가동률 및 운영 안전 가드")
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
        st.subheader("💰 운영 비용 설정 (천원)")
        cost_fields = [
            ("v_c_reg", "정규 임금 (인/월)"), ("v_c_ot", "초과 근무 수당 (Hr)"),
            ("v_c_h", "신규 고용 비용 (인)"), ("v_c_l", "해고 비용 (인)"),
            ("v_c_inv", "재고 유지비 (개/월)"), ("v_c_back", "부재고 비용 (개/월)"),
            ("v_c_mat", "재료비 (개당)"), ("v_c_sub", "외주 하청 비용 (개당)")
        ]
        for k, label in cost_fields:
            c1, c2 = st.columns([3, 1])
            with c1: st.number_input(label, key=k)
            with c2: st.checkbox("고정", key=f"lock_{k}")

        st.markdown("---")
        st.subheader("📈 초기값 및 수요")
        c1, c2 = st.columns([3, 1])
        with c1: demand_raw = st.text_input("6개월 수요 예측 (쉼표 구분)", key="demand_raw")
        with c2: st.checkbox("고정", key="lock_demand_raw")
        demand = [float(d.strip()) for d in demand_raw.split(",") if d.strip()]
        
        init_fields = [("v_w_init", "현재 근로자 수"), ("v_i_init", "현재고 수준"), ("v_i_final", "기말 목표 재고")]
        for k, label in init_fields:
            c1, c2 = st.columns([3, 1])
            with c1: st.number_input(label, key=k)
            with c2: st.checkbox("고정", key=f"lock_{k}")
            
    return demand, enable_sub, std_time, working_days, ot_limit

def render_supply_demand_tab(m, utils, demand):
    """Tab 1: 공급망 운영 가시성"""
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
    k2.metric("평균 가동률", f"{sum(utils)/len(utils):.1f}%")
    k3.metric("인력 고용/해고", f"+{sum(m.H[t]() for t in range(1,len(demand)+1)):.0f} / -{sum(m.L[t]() for t in range(1,len(demand)+1)):.0f}명")
    k4.metric("총 부재고 리스크", f"{sum(m.S[t]() for t in range(1,len(demand)+1)):,.0f}ea")

    st.subheader("📊 생산/수요/재고 통합 흐름")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.P[t]() for t in range(1,len(demand)+1)], name="자체 생산", marker_color='royalblue'))
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.C[t]() for t in range(1,len(demand)+1)], name="외주 하청", marker_color='lightslategray'))
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.S[t]() for t in range(1,len(demand)+1)], name="부재고", marker_color='crimson', opacity=0.8))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=demand, name="예상 수요", line=dict(color='darkorange', dash='dash')))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=[m.I[t]() for t in range(1,len(demand)+1)], name="재고 수준", yaxis="y2", line=dict(color='green', width=2.5)))
    
    min_i = st.session_state.get('min_inv', 0.0)
    if min_i > 0:
        fig.add_hline(y=min_i, line_dash="dot", line_color="#27AE60", annotation_text="최소 재고 가이드", yref="y2")
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("👷 인력 배치 및 고용/해고 동태")
    worker_counts = [int(m.W[t]()) for t in range(1, len(demand) + 1)]
    hired = [int(m.H[t]()) for t in range(1, len(demand) + 1)]
    fired = [int(m.L[t]()) for t in range(1, len(demand) + 1)]
    fig_w = go.Figure()
    fig_w.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=hired, name="신규 고용", marker_color="#3498DB"))
    fig_w.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[-x for x in fired], name="해고 처리", marker_color="#E67E22"))
    fig_w.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=worker_counts, mode="lines+markers", name="총 가동 인원", line=dict(color="#1ABC9C", width=3)))
    st.plotly_chart(fig_w, use_container_width=True)

def render_risk_efficiency_tab(m, utils, demand):
    """Tab 2: 리스크 및 비용 효율성 진단 (한자 수정 및 TypeError 해결본)"""
    st.subheader("📉 운영 리스크 및 효율성 종합 진단")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 💰 세부 비용 구조")
        v = st.session_state
        costs = {
            "노무비": sum(v['v_c_reg']*m.W[t]() + v['v_c_ot']*m.O[t]() for t in range(1,len(demand)+1)),
            "인사비": sum(v['v_c_h']*m.H[t]() + v['v_c_l']*m.L[t]() for t in range(1,len(demand)+1)),
            "재고비": sum(v['v_c_inv']*m.I[t]() + v['v_c_back']*m.S[t]() for t in range(1,len(demand)+1)),
            "생산비": sum(v['v_c_mat']*m.P[t]() + v['v_c_sub']*m.C[t]() for t in range(1,len(demand)+1))
        }
        st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)
    with c2:
        st.markdown("##### ⚠️ 생산 가동률 추이")
        fig_u = px.area(x=[f"{t}월" for t in range(1,len(demand)+1)], y=utils, title="가동률 (%)", markers=True)
        fig_u.add_hline(y=st.session_state.get('max_util', 100), line_dash="dot", line_color="red")
        st.plotly_chart(fig_u, use_container_width=True)

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### ⏳ 인력 과로 위험 (잔업 잠식률)")
        ot_lim = v.get('ot_limit', 10)
        burn_rates = [((m.O[t]() / (ot_lim * m.W[t]())) * 100 if m.W[t]() > 0 and ot_lim > 0 else 0) for t in range(1, len(demand)+1)]
        # TypeError 수정: marker_color 제거
        fig_ot = px.bar(x=[f"{t}월" for t in range(1,len(demand)+1)], y=burn_rates, color_discrete_sequence=['#E74C3C'])
        st.plotly_chart(fig_ot, use_container_width=True)
    with c4:
        st.markdown("##### 💸 단위 노무비 효율 (천원/ea)")
        unit_c = [((v['v_c_reg']*m.W[t]() + v['v_c_ot']*m.O[t]())/m.P[t]() if m.P[t]() > 0 else 0) for t in range(1, len(demand)+1)]
        st.plotly_chart(px.line(x=[f"{t}월" for t in range(1,len(demand)+1)], y=unit_c, markers=True), use_container_width=True)

def render_data_master_tab(m, utils, demand):
    """Tab 3: 정밀 데이터 마스터"""
    st.subheader("📋 총괄생산계획 정밀 데이터 명세")
    ds = []
    for t in range(1, len(demand) + 1):
        ds.append({
            "월": f"{t}월", "예상수요": demand[t-1], "자체생산": m.P[t](), "외주하청": m.C[t](), 
            "인력수": m.W[t](), "연장근로(Hr)": m.O[t](), "재고량": m.I[t](), "부재고": m.S[t](), "가동률": f"{utils[t-1]:.1f}%"
        })
    st.dataframe(pd.DataFrame(ds).set_index("월"), use_container_width=True)
