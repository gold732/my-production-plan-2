import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def render_sidebar():
    """모든 기초 파라미터와 락(Lock) 기능을 포함한 마스터 사이드바"""
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
    
    # 가동률 경고 표시 (100% 인접 시 빨간색 표시)
    avg_u = sum(utils)/len(utils)
    k2.metric("평균 가동률", f"{avg_u:.1f}%", delta="-Burnout 위험" if avg_u > 95 else None, delta_color="inverse")
    
    k3.metric("인력 고용/해고", f"+{sum(m.H[t]() for t in range(1,len(demand)+1)):.0f} / -{sum(m.L[t]() for t in range(1,len(demand)+1)):.0f}명")
    k4.metric("총 부재고", f"{sum(m.S[t]() for t in range(1,len(demand)+1)):,.0f}ea")

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

    st.subheader("👷 인력 최적 배치 및 고용/해고 트렌드")
    worker_counts = [int(m.W[t]()) for t in range(1, len(demand) + 1)]
    hired = [int(m.H[t]()) for t in range(1, len(demand) + 1)]
    fired = [int(m.L[t]()) for t in range(1, len(demand) + 1)]
    fig_w = go.Figure()
    fig_w.add_trace(go.Bar(x=[f"{t}월" for t in range(1,len(demand)+1)], y=hired, name="신규 고용 (+)", marker_color="#3498DB"))
    fig_w.add_trace(go.Bar(x=[f"{t}월" for t in range(1,len(demand)+1)], y=[-x for x in fired], name="해고 처리 (-)", marker_color="#E67E22"))
    fig_w.add_trace(go.Scatter(x=[f"{t}월" for t in range(1,len(demand)+1)], y=worker_counts, mode="lines+markers+text", name="총 가동 인원", text=worker_counts, textposition="top center", line=dict(color="#1ABC9C", width=4)))
    fig_w.update_layout(barmode='overlay', hovermode="x unified")
    st.plotly_chart(fig_w, use_container_width=True)

def render_risk_efficiency_tab(m, utils, demand):
    """2번 탭: 정밀 리스크 및 효율 대시보드"""
    st.subheader("📉 생산 운영 리스크 및 효율성 종합 진단")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 💰 세부 비용 구조")
        v = st.session_state
        costs = { "노무비": sum(v['v_c_reg']*m.W[t]() + v['v_c_ot']*m.O[t]() for t in range(1,len(demand)+1)),
                  "인사비": sum(v['v_c_h']*m.H[t]() + v['v_c_l']*m.L[t]() for t in range(1,len(demand)+1)),
                  "재고/부재고": sum(v['v_c_inv']*m.I[t]() + v['v_c_back']*m.S[t]() for t in range(1,len(demand)+1)),
                  "생산/외주": sum(v['v_c_mat']*m.P[t]() + v['v_c_sub']*m.C[t]() for t in range(1,len(demand)+1)) }
        st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)
    with c2:
        st.markdown("##### ⚠️ 생산 가동률 변동 추이")
        fig_u = px.area(x=[f"{t}월" for t in range(1,len(demand)+1)], y=utils, markers=True, labels={'y':'가동률 (%)','x':'월'})
        # 100% 라인 강조
        fig_u.add_hline(y=100, line_dash="solid", line_color="darkred", annotation_text="절대 한계선 (100%)")
        max_limit = st.session_state.get('max_util', 100)
        if max_limit < 100:
            fig_u.add_hline(y=max_limit, line_dash="dot", line_color="orange", annotation_text="설정 상한")
        st.plotly_chart(fig_u, use_container_width=True)

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### ⏳ 인력 번아웃 리스크 (잔업 잠식률)")
        ot_lim = v.get('ot_limit', 10)
        burn = [((m.O[t]() / (ot_lim * m.W[t]())) * 100 if m.W[t]() > 0 and ot_lim > 0 else 0) for t in range(1, len(demand)+1)]
        fig_ot = px.bar(x=[f"{t}월" for t in range(1,len(demand)+1)], y=burn, labels={'y':'한도 대비 잠식률 (%)','x':'월'}, color=burn, color_continuous_scale="OrRd")
        fig_ot.add_hline(y=100, line_dash="dash", line_color="darkred", annotation_text="위험 임계점")
        st.plotly_chart(fig_ot, use_container_width=True)
    with c4:
        st.markdown("##### 💸 단위 노무비 효율성 (천원/ea)")
        unit_c = [((v['v_c_reg']*m.W[t]() + v['v_c_ot']*m.O[t]())/m.P[t]() if m.P[t]() > 0 else 0) for t in range(1, len(demand)+1)]
        fig_unit = px.line(x=[f"{t}월" for t in range(1,len(demand)+1)], y=unit_c, markers=True, labels={'y':'단위당 노무 원가','x':'월'})
        fig_unit.update_traces(line=dict(color='#8E44AD', width=3))
        st.plotly_chart(fig_unit, use_container_width=True)

def render_data_master_tab(m, utils, demand):
    """3번 탭: 정밀 데이터 마스터"""
    st.subheader("📋 총괄생산계획 정밀 데이터 명세 (Raw Data)")
    ds = []
    for t in range(1, len(demand) + 1):
        ds.append({ "월": f"{t}월", "예상수요": demand[t-1], "자체생산": m.P[t](), "외주하청": m.C[t](), 
                    "인력수": m.W[t](), "연장근로(Hr)": m.O[t](), "재고량": m.I[t](), "부재고": m.S[t](), "가동률": f"{utils[t-1]:.1f}%" })
    st.dataframe(pd.DataFrame(ds).set_index("월"), use_container_width=True)
