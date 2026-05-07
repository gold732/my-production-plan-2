import streamlit st
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
        with c1: std_time = st.slider("제품당 표준 작업 시간 (Hr)", 1.0, 10.0, key="std_time")
        with c2: st.checkbox("고정", key="lock_std_time")
        
        c1, c2 = st.columns([3, 1])
        with c1: working_days = st.slider("월간 가동 일수", 1, 30, key="working_days")
        with c2: st.checkbox("고정", key="lock_working_days")
        
        c1, c2 = st.columns([3, 1])
        with c1: ot_limit = st.slider("인당 월간 초과근무 제한 (Hr)", 0, 30, key="ot_limit")
        with c2: st.checkbox("고정", key="lock_ot_limit")

        # [🚨 신규 추가] 최대 허용 가동률 제약 제어 위젯 레이어
        st.markdown("---")
        st.subheader("🛡️ 가동률 안전 가드")
        c1, c2 = st.columns([3, 1])
        with c1: max_util = st.slider("최대 허용 가동률 (%)", 50.0, 100.0, key="max_util")
        with c2: st.checkbox("고정", key="lock_max_util")

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
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 운영 비용", f"{m.cost():,.0f}k")
    k2.metric("평균 가동률", f"{sum(utils)/len(utils):.1f}%")
    k3.metric("인력 변동 수", f"{sum(m.H[t]() + m.L[t]() for t in range(1,len(demand)+1)):.0f}명")
    k4.metric("기말 재고량", f"{m.I[len(demand)]():,.0f}ea")

    st.subheader("📈 월별 생산/수요/재고 흐름")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.P[t]() for t in range(1,len(demand)+1)], name="자체 생산", marker_color='royalblue'))
    fig.add_trace(go.Bar(x=list(range(1,len(demand)+1)), y=[m.C[t]() for t in range(1,len(demand)+1)], name="외주 하청", marker_color='lightslategray'))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=demand, name="예상 수요", line=dict(color='crimson', dash='dash')))
    fig.add_trace(go.Scatter(x=list(range(1,len(demand)+1)), y=[m.I[t]() for t in range(1,len(demand)+1)], name="재고 수준", yaxis="y2", line=dict(color='orange')))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='stack', hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.subheader("💰 비용 세부 구성")
        v_c_reg = st.session_state['v_c_reg']
        v_c_inv = st.session_state['v_c_inv']
        v_c_mat = st.session_state['v_c_mat']
        v_c_sub = st.session_state['v_c_sub']
        
        costs = {
            "노무비": sum(v_c_reg*m.W[t]() for t in range(1,len(demand)+1)), 
            "재고비": sum(v_c_inv*m.I[t]() for t in range(1,len(demand)+1)), 
            "재료비": sum(v_c_mat*m.P[t]() for t in range(1,len(demand)+1)), 
            "외주비": sum(v_c_sub*m.C[t]() for t in range(1,len(demand)+1)),
            "기타": m.cost() - sum((v_c_reg*m.W[t]() + v_c_inv*m.I[t]() + v_c_mat*m.P[t]() + v_c_sub*m.C[t]()) for t in range(1,len(demand)+1))
        }
        st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)
    with col_r:
        pass

    st.markdown("---")
    st.subheader("👷 월별 인력 운영 현황")
    worker_counts = [int(m.W[t]()) for t in range(1, len(demand) + 1)]
    df_worker = pd.DataFrame({"월": [f"{t}월" for t in range(1, len(demand) + 1)], "배치 인원 (명)": worker_counts})
    
    fig_worker = px.line(df_worker, x="월", y="배치 인원 (명)", markers=True, text="배치 인원 (명)", title="월별 가동 인력 변동 추이 (정밀 스케일 격자 적용)")
    fig_worker.update_traces(textposition="top center", line=dict(width=3, color="#1ABC9C"), marker=dict(size=8, symbol="circle"))
    
    w_min, w_max = min(worker_counts), max(worker_counts)
    margin = max(2, int((w_max - w_min) * 0.5)) if w_max != w_min else 5
    fig_worker.update_layout(yaxis=dict(range=[w_min - margin, w_max + margin], dtick=1, title="인원 수 (명)"), xaxis=dict(title="분석 대상 월"), hovermode="x unified")
    st.plotly_chart(fig_worker, use_container_width=True)

def render_risk_analysis(utils, demand):
    """
    가동률 분석 전용 area 차트를 그리는 컴포넌트 함수
    """
    st.subheader("⚠️ 운영 리스크 분석 (가동률)")
    fig_risk = px.area(x=list(range(1,len(demand)+1)), y=utils, title="生産 가동률 추이 (%)", markers=True)
    fig_risk.add_hline(y=100, line_dash="dot", line_color="red", annotation_text="위험(100%)", annotation_position="bottom right")
    st.plotly_chart(fig_risk, use_container_width=True)
