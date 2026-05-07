from pyomo.environ import *

def solve_production_plan(D, domain, reg, ot, h, l, inv, back, mat, sub, stime, wdays, ot_lim, w0, i0, ifinal, use_sub, max_util=100.0, min_inv=0.0, max_cost=99999999.0):
    m = ConcreteModel()
    T = range(1, len(D) + 1); TIME = range(0, len(D) + 1)
    m.W = Var(TIME, domain=domain); m.H = Var(TIME, domain=domain); m.L = Var(TIME, domain=domain)
    m.P = Var(TIME, domain=domain); m.I = Var(TIME, domain=domain); m.S = Var(TIME, domain=domain)
    m.C = Var(TIME, domain=domain); m.O = Var(TIME, domain=domain)

    # 외주 비용은 개당 비용(sub * m.C[t])으로 정확히 계산
    m.cost = Objective(expr=sum(reg*m.W[t] + ot*m.O[t] + h*m.H[t] + l*m.L[t] + 
                                inv*m.I[t] + back*m.S[t] + mat*m.P[t] + sub*m.C[t] for t in T), sense=minimize)
    
    m.c = ConstraintList()
    m.c.add(m.W[0] == w0); m.c.add(m.I[0] == i0); m.c.add(m.S[0] == 0)
    for t in T:
        m.c.add(m.W[t] == m.W[t-1] + m.H[t] - m.L[t])
        cap_reg = (1/stime) * 8 * wdays * m.W[t]
        m.c.add(m.P[t] <= cap_reg + (1/stime)*m.O[t]) 
        m.c.add(m.I[t] == m.I[t-1] + m.P[t] + m.C[t] - D[t-1] - m.S[t-1] + m.S[t]) 
        m.c.add(m.O[t] <= ot_lim * m.W[t])
        if not use_sub:
            m.c.add(m.C[t] == 0)
        m.c.add(m.P[t] * stime <= (max_util / 100.0) * 8 * wdays * m.W[t])
        m.c.add(m.I[t] >= min_inv)

    m.c.add(m.I[len(D)] >= ifinal); m.c.add(m.S[len(D)] == 0)
    
    # [🚨 신규 추가] 총 운영 비용 상한선 제약조건 (예산 바운더리 관리 기능)
    m.c.add(m.cost <= max_cost)

    result = SolverFactory('glpk').solve(m)
    return m, result
