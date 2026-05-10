import streamlit as st
from pyomo.environ import TerminationCondition, NonNegativeIntegers, NonNegativeReals
from datetime import datetime

from ai_consultant import get_ai_consultant, get_ai_analysis
from optimization_engine import solve_production_plan
from ui_components import (
    render_sidebar, render_supply_demand_tab, 
    render_risk_efficiency_tab, render_data_master_tab,
    render_scenario_history_tab
)

st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

# 1. 기초 파라미터 이니셜라이징
param_defaults = {
    'opt_mode': "정수계획법(IP)", 'enable_sub': True, 'std_time': 4.0, 'working_days': 20, 'ot_limit': 10,
    'max_util': 100.0, 'min_inv': 0.0, 'v_c_reg': 640.0, 'v_c_ot': 6.0,
    'v_c_h': 300.0, 'v_c_l': 500.0, 'v_c_inv': 2.0, 'v_c_back': 5.0, 'v_c_mat': 10.0, 'v_c_sub': 30.0,
    'v_w_init': 80.0, 'v_i_init': 1000.0, 'v_i_final': 500.0, 'demand_raw': "1600, 3000, 3200, 3800, 2200, 2200",
    'scenario_history': []
}
for k, v in param_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# 상태값 초기화
for key in ['messages', 'success', 'utils', 'trigger_reoptimize', 'ai_analysis']:
    if key not in st.session_state: st.session_state[key] = [] if key == 'messages' else None

# 2. 사이드바 및 최적화 실행
demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization():
    st.session_state['success'] = False
    try:
        cur_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        m, sol = solve_production_plan(
            demand, cur_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
            st.session_state['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
            st.session_state['enable_sub'], st.session_state['max_util'], st.session_state['min_inv']
        )
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['res'] = m; st.session_state['success'] = True
            st.session_state['utils'] = [(m.P[t]()*st.session_state['std_time']/(8*st.session_state['working_days']*m.W[t]())*100 if m.W[t]() > 0 else 0) for t in range(1, len(demand)+1)]
            
            # --- [시나리오 데이터 스냅샷 저장] ---
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            scenario_data = {
                "시나리오명": f"Scenario_{timestamp}",
                "알고리즘": st.session_state['opt_mode'],
                "총 비용(k)": round(m.cost(), 2),
                "평균 가동률(%)": round(sum(st.session_state['utils'])/len(st.session_state['utils']), 1),
                "총 부재고(ea)": sum(m.S[t]() for t in range(1, len(demand)+1)),
                "외주 허용": "허용" if enable_sub else "차단",
                "정규임금": st.session_state['v_c_reg'], "초과수당": st.session_state['v_c_ot'],
                "재고유지비": st.session_state['v_c_inv'], "부재고비용": st.session_state['v_c_back'],
                "고용비용": st.session_state['v_c_h'], "해고비용": st.session_state['v_c_l'],
                "재료비": st.session_state['v_c_mat'], "외주비": st.session_state['v_c_sub'],
                "최대허용가동률": st.session_state['max_util'], "최소재고량": st.session_state['min_inv']
            }
            st.session_state['scenario_history'].append(scenario_data)
            
            ctx_summary = f"비용:{m.cost():,.0f}, 가동률:{st.session_state['utils']}, 부재고:{sum(m.S[t]() for t in range(1,len(demand)+1))}"
            st.session_state['ai_analysis'] = get_ai_analysis(ctx_summary)
            st.toast("✅ 시나리오 기록 및 AI 분석 완료!")
        else: 
            st.error("❌ 최적해 없음: 현재 제약 조건 내에서는 수학적 해가 존재하지 않습니다.")
            
    except Exception as e: st.error(f"⚠️ 시스템 런타임 오류: {str(e)}")

if st.session_state.get('trigger_reoptimize'):
    st.session_state['trigger_reoptimize'] = False; run_optimization()

# 3. 5단 전문 탭 UI 배치
t1, t2, t3, t4, t5 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "📜 시나리오 이력", "💬 AI 전략 상담방"])

with t1:
    if st.button("🚀 생산계획 수립 실행"): run_optimization()
    if st.session_state.get('success'):
        render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)

with t2:
    if st.session_state.get('success'):
        render_risk_efficiency_tab(st.session_state['res'], st.session_state['utils'], demand)

with t3:
    if st.session_state.get('success'):
        render_data_master_tab(st.session_state['res'], st.session_state['utils'], demand)

with t4:
    render_scenario_history_tab()

with t5:
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 초기화"): st.session_state.messages = []; st.rerun()
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if prompt := st.chat_input("의사결정에 필요한 조언을 구하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            # 1. 현재 가동 상태 텍스트화
            u_str = ", ".join([f"{v:.1f}%" for v in st.session_state['utils']]) if st.session_state['utils'] else "N/A"
            current_status = f"현재 결과 가동률:[{u_str}] | 비용:{st.session_state['res'].cost() if st.session_state['res'] else 'N/A'}"
            
            # 2. 저장된 시나리오 이력을 AI가 이해하기 쉬운 텍스트 형식으로 변환 (임금, 재고비 등 상세 포함)
            history_text = ""
            if st.session_state.get('scenario_history'):
                history_text = "\n\n[저장된 시나리오 이력 리스트]\n"
                for s in st.session_state['scenario_history']:
                    history_text += (
                        f"- 시나리오명: {s['시나리오명']} (알고리즘: {s['알고리즘']})\n"
                        f"  ㄴ 결과: 총비용={s['총 비용(k)']}, 평균가동률={s['평균 가동률(%)']}%, 총부재고={s['총 부재고(ea)']}\n"
                        f"  ㄴ 설정값: 정규임금={s['정규임금']}, 재고비={s['재고유지비']}, 부재고비={s['부재고비용']}, "
                        f"외주비={s['외주비']}, 최대가동률제약={s['최대허용가동률']}%\n"
                    )
            
            # 3. 통합 컨텍스트 구성 및 AI 호출
            full_context = current_status + history_text
            res = get_ai_consultant(prompt, full_context)
            
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
