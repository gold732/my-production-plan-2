import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyomo.environ import value

def render_risk_efficiency_tab(m, utils, demand):
    """가동률 100% 초과(잔업 가동)를 직관적으로 보여주는 리스크 진단 탭"""
    st.subheader("📉 생산 운영 리스크 및 효율성 종합 진단")
    v = st.session_state
    T = range(1, len(demand) + 1)
    
    plot_data = []
    for i, t in enumerate(T):
        w_val = float(value(m.W[t]) or 0.0)
        ot_val = float(value(m.O[t]) or 0.0)
        p_val = float(value(m.P[t]) or 0.0)
        ot_limit = float(v.get('ot_limit', 10.0))
        
        # 잔업 잠식률 (Burnout): 법적/정책적 잔업 한도를 얼마나 사용 중인가?
        ot_capacity = w_val * ot_limit
        burnout_rate = (ot_val / ot_capacity * 100.0) if ot_capacity > 0.1 else 0.0
        
        # 단위당 노무 원가
        unit_labor_cost = ((v['v_c_reg'] * w_val + v['v_c_ot'] * ot_val) / p_val) if p_val > 0.1 else 0.0
        
        plot_data.append({
            "월": f"{t}월",
            "가동률": utils[i],
            "번아웃_잠식률": round(burnout_rate, 2),
            "단위_노무비": round(unit_labor_cost, 2)
        })
    
    df = pd.DataFrame(plot_data)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 💰 세부 비용 구조")
        costs = { 
            "노무비": sum(v['v_c_reg']*float(value(m.W[t])) + v['v_c_ot']*float(value(m.O[t])) for t in T),
            "인사비": sum(v['v_c_h']*float(value(m.H[t])) + v['v_c_l']*float(value(m.L[t])) for t in T),
            "재고/부재고": sum(v['v_c_inv']*float(value(m.I[t])) + v['v_c_back']*float(value(m.S[t])) for t in T),
            "생산/외주": sum(v['v_c_mat']*float(value(m.P[t])) + v['v_c_sub']*float(value(m.C[t])) for t in T) 
        }
        st.plotly_chart(px.pie(names=list(costs.keys()), values=list(costs.values()), hole=0.4), use_container_width=True)

    with c2:
        st.markdown("##### ⚠️ 생산 가동률 변동 추이")
        # 100%를 넘는 가동률은 잔업이 발생했음을 의미
        fig_u = px.area(df, x="월", y="가동률", markers=True, labels={'가동률':'가동률 (%)'})
        fig_u.add_hline(y=100, line_dash="solid", line_color="darkred", annotation_text="정규 캐파 한계 (100%)")
        fig_u.update_layout(yaxis_range=[0, max(115, df['가동률'].max() + 10)])
        st.plotly_chart(fig_u, use_container_width=True)

    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### ⏳ 인력 번아웃 리스크 (잔업 잠식률)")
        fig_ot = px.bar(
            df, x="월", y="번아웃_잠식률", text=[f"{b}%" for b in df['번아웃_잠식률']],
            labels={'번아웃_잠식률':'잔업 한도 사용률 (%)'},
            color="번아웃_잠식률", color_continuous_scale="Reds", range_color=[0, 100]
        )
        fig_ot.update_traces(textposition='outside')
        fig_ot.add_hline(y=100, line_dash="dash", line_color="darkred", annotation_text="위험 임계점")
        fig_ot.update_layout(yaxis_range=[0, 130])
        st.plotly_chart(fig_ot, use_container_width=True)
        
    with c4:
        st.markdown("##### 💸 단위 노무비 효율성 (천원/ea)")
        fig_unit = px.line(df, x="월", y="단위_노무비", markers=True, labels={'단위_노무비':'단위당 노무 원가'})
        fig_unit.update_traces(line=dict(color='#8E44AD', width=3))
        st.plotly_chart(fig_unit, use_container_width=True)
