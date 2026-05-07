import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def render_sidebar():
    """
    사이드바의 모든 입력 제어 컨트롤 패널 컴포넌트를 분리 구체화한 함수
    """
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
        with c1: std_time = st.number_input("제품당 표준 작업 시간 (Hr)", min_value=1.0, max_value=10.0, step=0.1, key="std_time")
        with c2: st.checkbox("고정", key="lock_std_time")
        
        c1, c2 = st.columns([3, 1])
        with c1: working_days = st.slider("월간 가동 일수", 1, 30, key="working_days")
        with c2: st.checkbox("고정", key="lock_working_days")
        
        c1, c2 = st.columns([3, 1])
        with c1: ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 30, key="ot_limit")
        with c2: st.checkbox("고정", key="lock_ot_limit")

        st.markdown("---")
        st.subheader("🛡️ 가동률 및 운영 안전 가드")
        c1, c2 = st.columns([3, 1])
        with c1: max_util = st.number_input("최대 허용 가동률 (%)", min_value=50.0, max_value=100.0, step=0.5, key="max_util")
        with c2: st.checkbox("고정", key="lock_max_util")

        c1, c2 = st.columns([3, 1])
        with c1: min_inv = st.number_input("최소 유지 재고량 (ea)", min_value=0, max_value=10000, step=10, key="min_inv")
        with c2: st.checkbox("고정", key="lock_min_inv")

        c1, c2 = st.columns([3, 1])
        with c1: max_cost = st.number_input("최대 허용 총 비용 (천원)", min_value=0.0, step=1000.0, key="max_cost")
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
        demand = [float(d.strip()) for d in demand_raw.split(",")]
        
        init_fields = [
            ("v_w_init", "현재 근로자 수"), ("v_i_init", "현재고 수준"), ("v_i_final", "기말 목표 재고")
        ]
        for k, label in init_fields:
            c1, c2 = st.columns([3, 1])
            with c1: st.number_input(label, key=k)
            with c2: st.checkbox("고정", key=f"lock_{k}")
            
    return demand, enable_sub, std_time, working_days, ot_limit

def render_metrics_and_charts(m, utils, demand):
    """
    메인 운영 대시보드 탭의 카드 메트릭, 메인 혼합 바차트, 
    비용 파이차트 및 왜곡 보정 인력 차트를 렌더링하는 컴포넌트 함수
    """
    total_hired = sum(m.H[t]() for t in range(1, len(demand) + 1))
    total_fired = sum(m.L[t]() for t in range(1, len(demand) + 1))
    total_backlog = sum(m.S[t]() for t in range(1, len(demand) + 1))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
    k2.metric("평균 가동률", f"{sum(utils)/len(utils):.1f}%")
    k3.metric("인력 변동 (고용/해고)", f"+{total_hired:.0f} / -{total_fired:.0f} 명")
    k4.metric("총 부재고 발생량", f"{total_backlog:,.0f} ea")

    st.subheader("📈 월별 생산/수요/재고/부재고 통합 흐름")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.P[t]() for t in range(1,len(demand)+1)], name="자체 생산", marker_color='royalblue'))
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.C[t]() for t in range(1,len(demand)+1)], name="외주 하청", marker_color='lightslategray'))
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.S[t]() for t in range(1,len(demand)+1)], name="부재고 (미충족)", marker_color='crimson', opacity=0.8))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=demand, name="예상 수요", line=dict(color='darkorange', dash='dash')))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=[m.I[t]() for t in range(1,len(demand)+1)], name="재고 수준", yaxis="y2", line=dict(color='green', width=2.5)))
    
    # [🚨 신규 고도화] 설정한 최소 유지 재고량을 차트 우측(y2) 축 기준의 수평선으로 가시화하여 제약 충족 검증 지원
    current_min_inv = st.session_state.get('min_inv', 0.0)
    if current_min_inv > 0:
        fig.add_hline(y=current_min_inv, line_dash="dot", line_color="#27AE60", 
                      annotation_text=f"최소 유지 재고 ({current_min_inv:,.0f}ea)", 
                      annotation_position="top left", yref="y2")

    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("💰 세부 비용 구조 분석")
        v_c_reg = st.session_state['v_c_reg']
        v_c_ot = st.session_state['v_c_ot']
        v_c_h = st.session_state['v_c_h']
        v_c_l = st.session_state['v_c_l']
        v_c_inv = st.session_state['v_c_inv']
        v_c_back = st.session_state['v_c_back']
        v_c_mat = st.session_state['v_c_mat']
        v_c_sub = st.session_state['v_c_sub']
        
        costs = {
            "정규 노무비": sum(v_c_reg*m.W[t]() for t in range(1,len(demand)+1)), 
            "연장 근로비": sum(v_c_ot*m.O[t]() for t in range(1,len(demand)+1)),
            "인사 변동비(고용/해고)": sum(v_c_h*m.H[t]() + v_c_l*m.L[t]() for t in range(1,len(demand)+1)),
            "재고 유지비": sum(v_c_inv*m.I[t]() for t in range(1,len(demand)+1)), 
            "부재고 페널티": sum(v_c_back*m.S[t]() for t in range(1,len(demand)+1)),
            "순수 재료비": sum(v_c_mat*m.P[t]() for t in range(1,len(demand)+1)), 
            "외주 하청비": sum(v_c_sub*m.C[t]() for t in range(1,len(demand)+1))
        }
        cleaned_costs = {k: v for k, v in costs.items() if v > 0}
        st.plotly_chart(px.pie(names=list(cleaned_costs.keys()), values=list(cleaned_costs.values()), hole=0.4), use_container_width=True)
    with col_r:
        st.subheader("⏳ 월별 총 연장근로(Overtime) 활용 추이")
        ot_hours = [m.O[t]() for t in range(1, len(demand) + 1)]
        df_ot = pd.DataFrame({"월": [f"{t}월" for t in range(1, len(demand) + 1)], "연장근로 시간 (Hr)": ot_hours})
        fig_ot = px.bar(df_ot, x="월", y="연장근로 시간 (Hr)", text="연장근로 시간 (Hr)", color_discrete_sequence=["#E74C3C"])
        fig_ot.update_traces(texttemplate='%{text:.1f} Hr', textposition='outside')
        st.plotly_chart(fig_ot, use_container_width=True)

    st.markdown("---")
    st.subheader("👷 인력 최적 배치 및 고용/해고 트렌드 동태")
    worker_counts = [int(m.W[t]()) for t in range(1, len(demand) + 1)]
    hired_counts = [int(m.H[t]()) for t in range(1, len(demand) + 1)]
    fired_counts = [int(m.L[t]()) for t in range(1, len(demand) + 1)]
    df_labor = pd.DataFrame({
        "월": [f"{t}월" for t in range(1, len(demand) + 1)],
        "배치 인원 (명)": worker_counts,
        "신규 고용 (명)": hired_counts,
        "해고 인원 (명)": fired_counts
    })
    
    fig_worker = go.Figure()
    fig_worker.add_trace(go.Bar(x=df_labor["월"], y=df_labor["신규 고용 (명)"], name="신규 고용 (+명)", marker_color="#3498DB"))
    fig_worker.add_trace(go.Bar(x=df_labor["월"], y=[-x for x in df_labor["해고 인원 (명)"]], name="해고 처리 (-명)", marker_color="#E67E22"))
    fig_worker.add_trace(go.Scatter(x=df_labor["월"], y=df_labor["배치 인원 (명)"], mode="lines+markers+text", name="총 가동 인원수", text=df_labor["배치 인원 (명)"], textposition="top center", line=dict(width=3, color="#1ABC9C")))
    fig_worker.update_layout(barmode='overlay', hovermode="x unified")
    st.plotly_chart(fig_worker, use_container_width=True)

    st.markdown("---")
    with st.expander("📋 총괄생산계획(S&OP) 정밀 데이터 마스터 요약 시트"):
        data_sheet = []
        for t in range(1, len(demand) + 1):
            data_sheet.append({
                "분석 월": f"{t}월",
                "예상 수요 (ea)": demand[t-1],
                "자체 생산량 (ea)": m.P[t](),
                "외주 하청량 (ea)": m.C[t](),
                "연장근로 시간 (Hr)": m.O[t](),
                "총 가동 인력 (명)": m.W[t](),
                "당월 신규 고용 (명)": m.H[t](),
                "당월 해고 인원 (명)": m.L[t](),
                "월말 재고 수준 (ea)": m.I[t](),
                "미충족 부재고 (ea)": m.S[t](),
                "설비 생산 가동률": utils[t-1]
            })
        df_sheet = pd.DataFrame(data_sheet)
        st.dataframe(df_sheet.style.format({
            "예상 수요 (ea)": "{:,.0f}", "자체 생산량 (ea)": "{:,.0f}", "외주 하청량 (ea)": "{:,.0f}",
            "연장근로 시간 (Hr)": "{:,.1f}", "총 가동 인력 (명)": "{:.0f}", "당월 신규 고용 (명)": "{:.0f}",
            "당월 해고 인원 (명)": "{:.0f}", "월말 재고 수준 (ea)": "{:,.0f}", "미충족 부재고 (ea)": "{:,.0f}",
            "설비 생산 가동률": "{:,.1f}%"
        }), use_container_width=True)

def render_risk_analysis(utils, demand):
    """
    가동률 분석 전용 area 차트를 그리는 컴포넌트 함수
    """
    # [🚨 한자 수정 및 고도화] '生産' 오타를 깔끔한 한글 '생산'으로 변경하고, 사용자가 기입한 max_util 수치를 동적 가이드 점선으로 표출
    st.subheader("⚠️ 운영 리스크 분석 (가동률)")
    fig_risk = px.area(x=list(range(1,len(demand)+1)), y=utils, title="생산 가동률 추이 (%)", markers=True)
    
    current_max_util = st.session_state.get('max_util', 100.0)
    fig_risk.add_hline(y=current_max_util, line_dash="dot", line_color="red", 
                       annotation_text=f"최대 허용 가드라인 ({current_max_util:.1f}%)", 
                       annotation_position="bottom right")
    st.plotly_chart(fig_risk, use_container_width=True)
