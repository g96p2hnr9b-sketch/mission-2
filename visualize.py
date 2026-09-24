import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from parser import parse_vrp
from solver import solve_multistart


def plot_solution(instance, sol, outpath):
    fig, ax = plt.subplots(figsize=(7, 6))
    depot = instance.depot
    dx, dy = instance.coords[depot]
    colors = plt.cm.tab10.colors

    for i, route in enumerate(sol.routes):
        nodes = [depot] + route + [depot]
        xs = [instance.coords[n][0] for n in nodes]
        ys = [instance.coords[n][1] for n in nodes]
        ax.plot(xs, ys, "-o", color=colors[i % len(colors)], markersize=5,
                linewidth=1.8, label=f"Route {i+1} (load {sol.route_load(route)})")

    ax.scatter([dx], [dy], c="black", marker="s", s=140, zorder=5, label="Depot")
    for n, (x, y) in instance.coords.items():
        ax.annotate(str(n), (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")

    cost = sol.total_cost()
    gap = (cost - instance.optimal) / instance.optimal * 100 if instance.optimal else None
    ax.set_title(f"{instance.name}  |  Cost={cost:.2f}  Optimal={instance.optimal}  "
                 f"Gap={gap:.2f}%  Vehicles={len(sol.routes)}/{instance.num_vehicles}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=8)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    import glob, os
    os.makedirs("/mnt/user-data/outputs", exist_ok=True)
    results = []
    for fp in sorted(glob.glob("data/*.vrp")):
        inst = parse_vrp(fp)
        sol = solve_multistart(inst, verbose=False, n_starts=6, iterations=250)
        feas, errs = sol.is_feasible()
        cost = sol.total_cost()
        gap = (cost - inst.optimal) / inst.optimal * 100
        outpath = f"/mnt/user-data/outputs/{inst.name}_route.png"
        plot_solution(inst, sol, outpath)
        results.append((inst, sol, feas, cost, gap))
        print(f"{inst.name}: cost={cost:.2f} optimal={inst.optimal} gap={gap:.2f}% "
              f"feasible={feas} vehicles={len(sol.routes)}/{inst.num_vehicles} -> {outpath}")
