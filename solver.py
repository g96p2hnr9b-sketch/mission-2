"""
CVRP Solver — One Central Solver ที่ใช้ได้กับทุก instance (dynamic, ไม่ hardcode)

Algorithm:
  1. Construction: Clarke-Wright Savings Algorithm
  2. Improvement:   2-opt (intra-route) + Or-opt (move 1-3 consecutive nodes,
                    ทั้ง intra-route และ inter-route)
  3. Repair:        ถ้าจำนวน route เกิน k คัน จะ merge/reinsert route ที่เล็กที่สุด
                    เข้า route อื่นที่มีที่ว่างพอ (rare, safety net)

ผลลัพธ์: feasible routes, total cost, gap% เทียบ optimal
"""
import itertools
import random
from parser import CVRPInstance


class Solution:
    def __init__(self, instance: CVRPInstance, routes):
        self.instance = instance
        self.routes = routes  # list of list[node_id], ไม่รวม depot

    def route_cost(self, route):
        inst = self.instance
        d = inst.depot
        nodes = [d] + route + [d]
        return sum(inst.dist(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1))

    def route_load(self, route):
        return sum(self.instance.demands[n] for n in route)

    def total_cost(self):
        return sum(self.route_cost(r) for r in self.routes)

    def is_feasible(self, verbose=False):
        inst = self.instance
        errors = []
        served = []
        for r in self.routes:
            served.extend(r)
            load = self.route_load(r)
            if load > inst.capacity:
                errors.append(f"Route load {load} > capacity {inst.capacity}: {r}")
        if sorted(served) != sorted(inst.customers):
            missing = set(inst.customers) - set(served)
            dupes = [n for n in set(served) if served.count(n) > 1]
            if missing:
                errors.append(f"Missing customers: {missing}")
            if dupes:
                errors.append(f"Duplicate customers: {dupes}")
        if len(self.routes) > inst.num_vehicles:
            errors.append(f"Uses {len(self.routes)} vehicles > allowed {inst.num_vehicles}")
        if verbose and errors:
            for e in errors:
                print("  [INFEASIBLE]", e)
        return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# 1. Construction: Clarke-Wright Savings Algorithm
# ---------------------------------------------------------------------------
def clarke_wright(instance: CVRPInstance):
    depot = instance.depot
    customers = instance.customers
    demands = instance.demands
    capacity = instance.capacity

    # ทุก customer เริ่มเป็น route เดี่ยว: depot -> c -> depot
    routes = {c: [c] for c in customers}
    route_of = {c: c for c in customers}  # customer -> route key
    load = {c: demands[c] for c in customers}

    # savings(i, j) = d(depot,i) + d(depot,j) - d(i,j)
    savings = []
    for i, j in itertools.combinations(customers, 2):
        s = instance.dist(depot, i) + instance.dist(depot, j) - instance.dist(i, j)
        savings.append((s, i, j))
    savings.sort(reverse=True, key=lambda t: t[0])

    for s, i, j in savings:
        ri, rj = route_of[i], route_of[j]
        if ri == rj:
            continue
        route_i, route_j = routes[ri], routes[rj]
        # merge ได้เฉพาะเมื่อ i อยู่ปลาย route_i และ j อยู่ต้น route_j (หรือกลับกัน)
        # และ i, j เป็น "endpoint" (ติด depot) ของ route ตัวเอง
        i_is_start, i_is_end = route_i[0] == i, route_i[-1] == i
        j_is_start, j_is_end = route_j[0] == j, route_j[-1] == j
        if not (i_is_start or i_is_end) or not (j_is_start or j_is_end):
            continue
        if load[ri] + load[rj] > capacity:
            continue

        # สร้าง route ใหม่โดยต่อให้ i กับ j อยู่ติดกันตรงกลาง
        if i_is_end and j_is_start:
            new_route = route_i + route_j
        elif i_is_start and j_is_end:
            new_route = route_j + route_i
        elif i_is_end and j_is_end:
            new_route = route_i + route_j[::-1]
        elif i_is_start and j_is_start:
            new_route = route_i[::-1] + route_j
        else:
            continue

        new_key = ri
        routes[new_key] = new_route
        load[new_key] = load[ri] + load[rj]
        for n in new_route:
            route_of[n] = new_key
        del routes[rj]
        del load[rj]

    final_routes = list(routes.values())

    # ---- Repair: ถ้าจำนวน route เกิน k คัน ให้ merge/insert route เล็กสุดเข้า route อื่น ----
    final_routes = _repair_vehicle_count(instance, final_routes)
    return final_routes


def _repair_vehicle_count(instance, routes):
    """ถ้า len(routes) > num_vehicles ให้พยายามยุบ route ที่เล็กที่สุดเข้า route อื่น
    โดยแทรกลูกค้าแต่ละคนที่ตำแหน่งที่ cost เพิ่มน้อยที่สุด (cheapest insertion),
    เคารพ capacity เสมอ"""
    routes = [r[:] for r in routes]
    while len(routes) > instance.num_vehicles:
        routes.sort(key=lambda r: sum(instance.demands[n] for n in r))
        small = routes.pop(0)
        for cust in small:
            best = None
            for ri, r in enumerate(routes):
                load = sum(instance.demands[n] for n in r)
                if load + instance.demands[cust] > instance.capacity:
                    continue
                for pos in range(len(r) + 1):
                    trial = r[:pos] + [cust] + r[pos:]
                    cost_before = _route_cost(instance, r)
                    cost_after = _route_cost(instance, trial)
                    delta = cost_after - cost_before
                    if best is None or delta < best[0]:
                        best = (delta, ri, pos)
            if best is None:
                # ไม่มีที่ใส่ได้เลย -> เปิด route ใหม่ (violates k, จะ flag เป็น infeasible)
                routes.append([cust])
            else:
                _, ri, pos = best
                routes[ri] = routes[ri][:pos] + [cust] + routes[ri][pos:]
    return routes


def _route_cost(instance, route):
    d = instance.depot
    nodes = [d] + route + [d]
    return sum(instance.dist(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1))


# ---------------------------------------------------------------------------
# 2. Improvement: 2-opt (intra-route)
# ---------------------------------------------------------------------------
def two_opt(instance, route):
    if len(route) < 4:
        return route
    improved = True
    best = route[:]
    while improved:
        improved = False
        d = instance.depot
        nodes = [d] + best + [d]
        n = len(nodes)
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                a, b, c, e = nodes[i - 1], nodes[i], nodes[j], nodes[j + 1]
                old = instance.dist(a, b) + instance.dist(c, e)
                new = instance.dist(a, c) + instance.dist(b, e)
                if new < old - 1e-9:
                    nodes[i:j + 1] = nodes[i:j + 1][::-1]
                    improved = True
        best = nodes[1:-1]
    return best


# ---------------------------------------------------------------------------
# 3. Improvement: Or-opt (ย้าย chunk 1-3 nodes ไปแทรกที่อื่น, intra + inter route)
# ---------------------------------------------------------------------------
def or_opt(instance, routes, max_chunk=3):
    routes = [r[:] for r in routes]
    improved = True
    while improved:
        improved = False
        for src_idx, src in enumerate(routes):
            for size in range(1, min(max_chunk, len(src)) + 1):
                for start in range(len(src) - size + 1):
                    chunk = src[start:start + size]
                    remainder = src[:start] + src[start + size:]
                    chunk_load = sum(instance.demands[n] for n in chunk)
                    cost_removed = _route_cost(instance, src) - _route_cost(instance, remainder)

                    best_delta = -1e-9
                    best_move = None
                    for dst_idx, dst in enumerate(routes):
                        if dst_idx == src_idx:
                            base = remainder
                        else:
                            dst_load = sum(instance.demands[n] for n in dst)
                            if dst_load + chunk_load > instance.capacity:
                                continue
                            base = dst
                        for pos in range(len(base) + 1):
                            if dst_idx == src_idx and start <= pos <= start + size:
                                continue  # ตำแหน่งเดิม/ทับซ้อน
                            trial = base[:pos] + chunk + base[pos:]
                            cost_added = _route_cost(instance, trial) - _route_cost(instance, base)
                            if dst_idx == src_idx:
                                delta = cost_added - cost_removed
                            else:
                                delta = (cost_added) - cost_removed
                            if delta < best_delta:
                                best_delta = delta
                                best_move = (dst_idx, pos)
                    if best_move is not None:
                        dst_idx, pos = best_move
                        if dst_idx == src_idx:
                            new_route = remainder[:pos] + chunk + remainder[pos:]
                            routes[src_idx] = new_route
                        else:
                            routes[src_idx] = remainder
                            routes[dst_idx] = routes[dst_idx][:pos] + chunk + routes[dst_idx][pos:]
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
    routes = [r for r in routes if r]  # ลบ route ว่าง
    return routes


def _local_search(instance, routes):
    """วน 2-opt + Or-opt จนกว่า cost จะไม่ลดลงอีก (ลู่เข้า local optimum)"""
    prev_cost = None
    for _ in range(15):
        routes = [two_opt(instance, r) for r in routes]
        routes = or_opt(instance, routes)
        cost = sum(_route_cost(instance, r) for r in routes)
        if prev_cost is not None and cost >= prev_cost - 1e-6:
            break
        prev_cost = cost
    routes = _repair_vehicle_count(instance, routes)
    routes = [two_opt(instance, r) for r in routes]
    return routes


def _segment_swap(instance, routes, rng):
    """สุ่มสลับ chunk (1-3 nodes) ระหว่าง 2 route ที่สุ่มมา — เช็ค capacity ก่อนรับ"""
    non_empty = [i for i, r in enumerate(routes) if len(r) >= 1]
    if len(non_empty) < 2:
        return routes
    i, j = rng.sample(non_empty, 2)
    ri, rj = routes[i], routes[j]
    si = rng.randint(1, min(3, len(ri)))
    sj = rng.randint(1, min(3, len(rj)))
    pi = rng.randint(0, len(ri) - si)
    pj = rng.randint(0, len(rj) - sj)
    chunk_i = ri[pi:pi + si]
    chunk_j = rj[pj:pj + sj]
    new_ri = ri[:pi] + chunk_j + ri[pi + si:]
    new_rj = rj[:pj] + chunk_i + rj[pj + sj:]
    load_i = sum(instance.demands[n] for n in new_ri)
    load_j = sum(instance.demands[n] for n in new_rj)
    if load_i <= instance.capacity and load_j <= instance.capacity:
        routes[i], routes[j] = new_ri, new_rj
    return routes


def _double_bridge_intra(instance, routes, rng):
    """Double-bridge แบบดั้งเดิมภายใน 1 route: ตัดเป็น 4 ท่อน A-B-C-D แล้วต่อใหม่ A-C-B-D
    (หนี local optimum ของ 2-opt ได้ดีเพราะ 2-opt เพียงอย่างเดียวทำ move แบบนี้ไม่ได้)"""
    candidates = [i for i, r in enumerate(routes) if len(r) >= 8]
    if not candidates:
        return routes
    idx = rng.choice(candidates)
    r = routes[idx][:]
    n = len(r)
    p1, p2, p3 = sorted(rng.sample(range(1, n), 3))
    routes[idx] = r[:p1] + r[p2:p3] + r[p1:p2] + r[p3:]
    return routes


def _perturb(instance, routes, rng, strength=(3, 6)):
    """Kick หลาย move ติดกัน (segment-swap / double-bridge) เพื่อหนี local optimum
    ให้แรงพอที่ local search จะไม่ลู่กลับไปจุดเดิม"""
    routes = [r[:] for r in routes]
    for _ in range(rng.randint(*strength)):
        if rng.random() < 0.6:
            routes = _segment_swap(instance, routes, rng)
        else:
            routes = _double_bridge_intra(instance, routes, rng)
    return routes


# ---------------------------------------------------------------------------
# Main solve function
# ---------------------------------------------------------------------------
def solve(instance: CVRPInstance, verbose=True, iterations=300, seed=42):
    routes = clarke_wright(instance)
    if verbose:
        sol0 = Solution(instance, routes)
        print(f"  [Construction/Clarke-Wright] cost={sol0.total_cost():.2f}, "
              f"routes={len(routes)}")

    routes = _local_search(instance, routes)
    best_routes = routes
    best_cost = sum(_route_cost(instance, r) for r in routes)
    if verbose:
        print(f"  [+2-opt/Or-opt converge]     cost={best_cost:.2f}")

    # ---- Iterated Local Search (basin-hopping):
    #      kick หลาย move -> local search -> รับถ้าดีขึ้น, บางครั้งรับที่แย่กว่าเพื่อ diversify ----
    rng = random.Random(seed)
    current = [r[:] for r in best_routes]
    no_improve = 0
    for _ in range(iterations):
        trial = _perturb(instance, current, rng)
        trial = _local_search(instance, trial)
        feas, _ = Solution(instance, trial).is_feasible()
        if not feas:
            no_improve += 1
            continue
        cost = sum(_route_cost(instance, r) for r in trial)
        if cost < best_cost - 1e-6:
            best_cost = cost
            best_routes = [r[:] for r in trial]
            current = [r[:] for r in trial]
            no_improve = 0
        elif rng.random() < 0.1:
            current = [r[:] for r in trial]  # ยอมรับคำตอบที่แย่กว่าเป็นครั้งคราวเพื่อหนี local optimum
            no_improve += 1
        else:
            current = [r[:] for r in best_routes]
            no_improve += 1
        if no_improve >= 40:
            current = [r[:] for r in best_routes]
            no_improve = 0

    if verbose:
        print(f"  [+Iterated Local Search]     cost={best_cost:.2f}")

    return Solution(instance, best_routes)


def solve_multistart(instance: CVRPInstance, verbose=True, n_starts=6,
                      iterations=250, base_seed=0):
    """รัน Iterated Local Search หลาย seed (multi-start metaheuristic) แล้วเลือกคำตอบที่ดีที่สุด
    ยังคง dynamic 100% — ไม่ผูกกับ instance ใดเป็นพิเศษ ใช้ได้กับทุกโจทย์ที่ป้อนเข้ามา"""
    best_sol = None
    best_cost = float("inf")
    for s in range(n_starts):
        sol = solve(instance, verbose=False, iterations=iterations, seed=base_seed + s)
        feas, _ = sol.is_feasible()
        if not feas:
            continue
        cost = sol.total_cost()
        if verbose:
            print(f"  [seed {base_seed + s}] cost={cost:.2f}")
        if cost < best_cost:
            best_cost = cost
            best_sol = sol
    return best_sol


if __name__ == "__main__":
    from parser import parse_vrp
    import glob

    for fp in sorted(glob.glob("data/*.vrp")):
        inst = parse_vrp(fp)
        print(f"\n=== {inst.name} (optimal={inst.optimal}) ===")
        sol = solve_multistart(inst, verbose=True, n_starts=6, iterations=250)
        feasible, errors = sol.is_feasible(verbose=True)
        cost = sol.total_cost()
        gap = (cost - inst.optimal) / inst.optimal * 100 if inst.optimal else None
        print(f"  Feasible: {feasible}")
        print(f"  Total cost: {cost:.2f}")
        print(f"  Optimal:    {inst.optimal}")
        print(f"  Gap:        {gap:.2f}%")
        print(f"  Vehicles used: {len(sol.routes)} / {inst.num_vehicles}")
        for i, r in enumerate(sol.routes, 1):
            load = sol.route_load(r)
            print(f"    Route {i}: Depot -> {' -> '.join(map(str, r))} -> Depot "
                  f"(load {load}/{inst.capacity})")
