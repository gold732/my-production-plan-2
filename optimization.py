from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub):
    """총괄생산계획(APP) 수리 모델 수립 및 해결"""
    m = ConcreteModel()
    T = range(1, len(D) + 1)
    TIME = range(0, len(D) + 1)
    
    # 변수 정의
    m.W = Var(TIME, domain=domain) # 인력
    m.H = Var(TIME, domain=domain) # 채용
    m.L = Var(TIME, domain=domain) # 해고
    m.P = Var(TIME, domain=domain) # 자체 생산량
    m.I = Var(TIME, domain=domain) # 재고
    m.S = Var(TIME, domain=domain) # 부재고(Backlog)
    m.C = Var(TIME, domain=domain) # 외주량
    m.O = Var(TIME, domain=domain) # 초과근무 시간

    # 목적함수: 총 비용 최소화
    m.cost = Objective(expr=sum(
        reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
        inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] 
        for t in T), sense=minimize)
    
    m.c = ConstraintList()
    m.c.add(m.W[0] == w0)
    m.c.add(m.I[0] == i0)
    m.c.add(m.S[0] == 0)
    
    for t in T:
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t]) # 인력 균형
        cap_reg = (1/stime) * 8 * wdays * m.W[t]
        m.c.add(m.P[t] <= cap_reg + (1/stime)*m.O[t]) # 생산 용량
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) # 재고 균형
        m.c.add(m.O[t] <= ot_lim * m.W[t]) # 초과근무 제한
        if not use_sub:
            m.c.add(m.C[t] == 0) # 외주 On/Off 제약

    m.c.add(m.I[len(D)] >= ifinal) # 기말 목표 재고
    m.c.add(m.S[len(D)] == 0)      # 최종 부재고 0
    
    result = SolverFactory('glpk').solve(m)
    return m, result
