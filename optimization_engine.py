from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub, max_util=100.0, min_inv=0.0):
    """수정된 S&OP 수리 모델: 초과 근무 생산 가동 보장 버전"""
    m = ConcreteModel()
    T = range(1, len(D) + 1); TIME = range(0, len(D) + 1)
    
    # 결정변수 선언
    m.W = Var(TIME, domain=domain); m.H = Var(TIME, domain=domain); m.L = Var(TIME, domain=domain)
    m.P = Var(TIME, domain=domain); m.I = Var(TIME, domain=domain); m.S = Var(TIME, domain=domain)
    m.C = Var(TIME, domain=domain); m.O = Var(TIME, domain=domain)

    # 목적함수: 총 운영 비용 최소화
    m.cost = Objective(expr=sum(reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
                                inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] for t in T), sense=minimize)
    
    m.c = ConstraintList()
    # 초기값 제약
    m.c.add(m.W[0] == w0); m.c.add(m.I[0] == i0); m.c.add(m.S[0] == 0)
    
    for t in T:
        # 노동력 균형 제약: Wt = Wt-1 + Ht - Lt
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t])
        
        # 생산 능력 및 초과근무 제약 (가동률 파라미터를 정규 캐파에 통합 적용)
        cap_reg = (max_util / 100.0) * (1/stime) * 8 * wdays * m.W[t]
        m.c.add(m.P[t] <= cap_reg + (1/stime)*m.O[t]) 
        m.c.add(m.O[t] <= ot_lim * m.W[t])
        
        # 재고 평형 제약: It = It-1 + Pt + Ct - Dt - St-1 + St
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) 
        
        if not use_sub: m.c.add(m.C[t] == 0)
        
        # 최소 유지 재고 제약
        m.c.add(m.I[t] >= min_inv)

    # 기말 목표치 제약
    m.c.add(m.I[len(D)] >= ifinal); m.c.add(m.S[len(D)] == 0)
    
    result = SolverFactory('glpk').solve(m)
    return m, result
