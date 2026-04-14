from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub):
    m = ConcreteModel()
    T = range(1, len(D) + 1); TIME = range(0, len(D) + 1)
    
    # 변수 정의
    m.W = Var(TIME, domain=domain); m.H = Var(TIME, domain=domain); m.L = Var(TIME, domain=domain)
    m.P = Var(TIME, domain=domain); m.I = Var(TIME, domain=domain); m.S = Var(TIME, domain=domain)
    m.C = Var(TIME, domain=domain); m.O = Var(TIME, domain=domain)

    # 목적함수
    m.cost = Objective(expr=sum(reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
                                inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] for t in T), sense=minimize)
    
    m.c = ConstraintList()
    m.c.add(m.W[0] == w0); m.c.add(m.I[0] == i0); m.c.add(m.S[0] == 0)
    
    for t in T:
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t])
        # 가동률 100% 초과 상황(초과근무 활용)에서도 모델이 뻗지 않도록 캡 용량 계산 방식 유지
        cap_reg = (1/stime) * 8 * wdays * m.W[t]
        m.c.add(m.P[t] <= cap_reg + (1/stime)*m.O[t]) 
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) 
        m.c.add(m.O[t] <= ot_lim * m.W[t])
        if not use_sub: m.c.add(m.C[t] == 0)

    m.c.add(m.I[len(D)] >= ifinal); m.c.add(m.S[len(D)] == 0)
    
    # 솔버 옵션 추가 (안정성 강화)
    solver = SolverFactory('glpk')
    result = solver.solve(m)
    return m, result
