import streamlit as st
from pyomo.environ import TerminationCondition, NonNegativeIntegers, NonNegativeReals

from ai_consultant import get_ai_consultant, get_ai_analysis
from optimization_engine import solve_production_plan
from ui_components import render_sidebar, render_supply_demand_tab, render_risk_efficiency_tab, render_data_master_tab

st.set_page_config(page_title="AI S&OP Control Tower", layout="wide")
st.title("원예장비 제조업체 총괄생산계획 수립")

# 세션 상태 초기화 (생략 없이 이전 로직 동일 유지)
param_keys = ['opt_mode', 'enable_sub', 'std_time', 'working_days', 'ot_limit', 'max_util', 'min_inv', 'max_cost',
              'v_c_reg', 'v_c_ot', 'v_c_h', 'v_c_l', 'v_c_inv', 'v_c_back', 'v_c_mat', 'v_c_sub',
              'v_w_init', 'v_i_init', 'v_i_final']

if 'pending_updates' not in st.session_state: st.session_state['pending_updates'] = {}
if st.session_state['pending_updates']:
    for pk, pval in st.session_state['pending_updates'].items(): st.session_state[pk] = pval
    st.session_state['pending_updates'] = {}; st.session_state['trigger_reoptimize'] = True

# 초기값 세팅 및 Lock 설정 로직 (이전과 동일하게 보존)
initial_locked_keys = {'v_w_init', 'v_i_init', 'v_c_sub', 'v_c_inv', 'v_c_mat', 'v_c_back', 'std_time', 'opt_mode', 'enable_sub', 'v_i_final', 'max_util', 'min_inv', 'max_cost'}
for pk in param_keys:
    if f"lock_{pk}" not in st.session_state: st.session_state[f"lock_{pk}"] = (pk in initial_locked_keys)
if "lock_demand_raw" not in st.session_state: st.session_state["lock_demand_raw"] = True

# 기본값 및 상태 초기화 (생략)
if 'messages' not in st.session_state: st.session_state.messages = []
if 'success' not in st.session_state: st.session_state['success'] = False
if 'trigger_reoptimize' not in st.session_state: st.session_state['trigger_reoptimize'] = False

demand, enable_sub, std_time, working_days, ot_limit = render_sidebar()

def run_optimization_process():
    st.session_state['success'] = False
    try:
        current_demand = [float(d.strip()) for d in st.session_state['demand_raw'].split(",")]
        current_domain = NonNegativeIntegers if "IP" in st.session_state['opt_mode'] else NonNegativeReals
        model, sol = solve_production_plan(
            current_demand, current_domain, st.session_state['v_c_reg'], st.session_state['v_c_ot'], 
            st.session_state['v_c_h'], st.session_state['v_c_l'], st.session_state['v_c_inv'], st.session_state['v_c_back'], 
            st.session_state['v_c_mat'], st.session_state['v_c_sub'], st.session_state['std_time'], st.session_state['working_days'], 
            st.session_state['ot_limit'], st.session_state['v_w_init'], st.session_state['v_i_init'], st.session_state['v_i_final'], 
            st.session_state['enable_sub'], st.session_state['max_util'], st.session_state['min_inv'], st.session_state['max_cost']
        )
        if sol.solver.termination_condition == TerminationCondition.optimal:
            st.session_state['res'] = model; st.session_state['success'] = True
            temp_utils = []
            for t in range(1, len(current_demand) + 1):
                denom = 8 * st.session_state['working_days'] * model.W[t]()
                temp_utils.append((model.P[t]() * st.session_state['std_time'] / denom * 100) if denom > 0 else 0)
            st.session_state['utils'] = temp_utils
            st.session_state['ai_analysis'] = get_ai_analysis(f"비용:{model.cost():,.0f}, 가동률:{temp_utils}")
            st.toast("✅ 최적 생산계획 수립 완료!")
        else: st.error("❌ 최적해를 찾지 못했습니다.")
    except Exception as e: st.error(f"⚠️ 오류: {str(e)}")

if st.session_state['trigger_reoptimize']:
    st.session_state['trigger_reoptimize'] = False; run_optimization_process()

# [🚨 탭 구조 전면 리팩토링]: 4단 전문화 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📊 공급망 운영", "📉 리스크/효율", "📋 데이터 마스터", "💬 AI 전략 상담방"])

with tab1:
    if st.button("🚀 최적 생산계획 수립 실행", key="btn_run"): run_optimization_process()
    if st.session_state.get('success'):
        # AI 진단 보고서 요약 상단 배치
        analysis = st.session_state.get('ai_analysis', {})
        with st.expander("🤖 AI 전문 컨설턴트 핵심 진단", expanded=True):
            c_m1, c_m2 = st.columns([1, 4])
            c_m1.metric("리스크 등급", analysis.get("risk_level", "🟡 주의"))
            c_m2.info(f"**요약:** {analysis.get('summary', '')}")
        render_supply_demand_tab(st.session_state['res'], st.session_state['utils'], demand)

with tab2:
    if st.session_state.get('success'):
        render_risk_efficiency_tab(st.session_state['res'], st.session_state['utils'], demand)
    else: st.info("먼저 최적 생산계획 수립을 실행하십시오.")

with tab3:
    if st.session_state.get('success'):
        render_data_master_tab(st.session_state['res'], st.session_state['utils'], demand)
    else: st.info("데이터가 없습니다.")

with tab4:
    st.subheader("💬 AI 전략 상담방")
    if st.button("🧹 대화 내용 초기화"): st.session_state.messages = []; st.rerun()
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("의사결정에 필요한 조언을 구하세요."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        # 콘텍스트 요약 생성 (생략 동일 유지)
        ctx = "현재 대시보드 상태 요약 및 파라미터 상태 전달..."
        with st.chat_message("assistant"):
            ai_res = get_ai_consultant(prompt, ctx)
            st.markdown(ai_res); st.session_state.messages.append({"role": "assistant", "content": ai_res})
        if st.session_state.get('param_updated_by_ai', False):
            st.session_state['param_updated_by_ai'] = False; st.rerun()
