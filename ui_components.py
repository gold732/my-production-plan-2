import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

def render_sidebar():
    """전문 용어 및 단위가 복구된 마스터 제어판"""
    with st.sidebar:
        st.header("🎮 시스템 제어판")
        opt_mode = st.radio("알고리즘 선택", ["정수계획법(IP)", "선형계획법(LP)"], key="opt_mode")

        st.markdown("---")
        st.subheader("🏭 공급망 전략")
        enable_sub = st.toggle("외주 하청 허용", key="enable_sub")

        st.markdown("---")
        st.subheader("⏱️ 공정 효율 및 기초 제약")
        std_time = st.number_input("제품당 표준 작업 시간 (Hr)", min_value=1.0, step=0.1, key="std_time")
        working_days = st.slider("월간 가동 일수 (일)", 1, 30, key="working_days")
        ot_limit = st.slider("인당 월간 초과근무 한도 (Hr)", 0, 100, key="ot_limit")

        st.markdown("---")
        st.subheader("🛡️ 운영 정책 및 생산 제약")
        max_util = st.number_input("최대 허용 가동률 (%)", min_value=1.0, max_value=100.0, step=0.5, key="max_util")
        min_inv = st.number_input("최소 유지 재고량 (ea)", min_value=0, key="min_inv")

        st.markdown("---")
        st.subheader("💰 운영 비용 설정 (단위: 천원)")
        costs = [
            ("v_c_reg", "정규 임금 (천원/인/월)"), ("v_c_ot", "초과 수당 (천원/시간)"), 
            ("v_c_h", "고용 비용 (천원/인)"), ("v_c_l", "해고 비용 (천원/인)"),
            ("v_c_inv", "재고 유지비 (천원/개/월)"), ("v_c_back", "부재고 비용 (천원/개/월)"), 
            ("v_c_mat", "제품 재료비 (천원/개)"), ("v_c_sub", "외주 하청비 (천원/개)")
        ]
        for k, lbl in costs:
            st.number_input(lbl, key=k)

        st.markdown("---")
        st.subheader("📈 기초 데이터 및 수요")
        demand_raw = st.text_input("수요 예측 (쉼표 구분, ea)", key="demand_raw")
        demand = [float(d.strip()) for d in demand_raw.split(",") if d.strip()]
        inits = [
            ("v_w_init", "기초 가용 인력 (명)"), 
            ("v_i_init", "기초 재고 수준 (ea)"), 
            ("v_i_final", "기말 목표 재고 (ea)")
        ]
        for k, lbl in inits:
            st.number_input(lbl, key=k)
            
    return demand, enable_sub, std_time, working_days, ot_limit

def render_supply_demand_tab(m, utils, demand):
    """1번 탭: 그래프 로직 완벽 복구"""
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
    """2번 탭: 리스크 가이드라인 로직 복구"""
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
    st.subheader("📋 총괄생산계획 정밀 데이터 명세 (Raw Data)")
    ds = []
    for t in range(1, len(demand) + 1):
        ds.append({ "월": f"{t}월", "예상수요": demand[t-1], "자체생산": m.P[t](), "외주하청": m.C[t](), 
                    "인력수": m.W[t](), "연장근로(Hr)": m.O[t](), "재고량": m.I[t](), "부재고": m.S[t](), "가동률": f"{utils[t-1]:.1f}%" })
    st.dataframe(pd.DataFrame(ds).set_index("월"), use_container_width=True)

def render_scenario_history_tab():
    """신규 추가: 시나리오 비교 및 이력 관리 탭"""
    st.subheader("📜 최적화 시나리오 수행 이력")
    
    if not st.session_state.get('scenario_history'):
        st.info("아직 기록된 시나리오가 없습니다. '생산계획 수립 실행' 버튼을 눌러 첫 번째 시나리오를 생성하세요.")
        return

    # 이력 데이터프레임 변환
    history_df = pd.DataFrame(st.session_state['scenario_history'])
    
    # 주요 지표 강조를 위한 스타일링 및 표시
    st.dataframe(history_df, use_container_width=True)

    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("🗑️ 모든 이력 삭제", type="secondary"):
            st.session_state['scenario_history'] = []
            st.rerun()
    
    st.markdown("---")
    st.subheader("📈 시나리오별 총 비용 비교")
    fig_comp = px.bar(history_df, x="시나리오명", y="총 비용(k)", color="알고리즘", 
                      text="총 비용(k)", title="시나리오별 운영 비용 추이")
    fig_comp.update_traces(texttemplate='%{text:,.0f}k', textposition='outside')
    st.plotly_chart(fig_comp, use_container_width=True)
