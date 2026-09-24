"""
CVRP .vrp file parser (CVRPLIB / Augerat format)
รองรับไฟล์รูปแบบ: NAME, COMMENT, TYPE, DIMENSION, EDGE_WEIGHT_TYPE, CAPACITY,
NODE_COORD_SECTION, DEMAND_SECTION, DEPOT_SECTION
"""
import re
import math


class CVRPInstance:
    def __init__(self, name, capacity, num_vehicles, coords, demands, depot_id, optimal=None):
        self.name = name
        self.capacity = capacity
        self.num_vehicles = num_vehicles
        self.coords = coords          # dict: node_id -> (x, y)
        self.demands = demands        # dict: node_id -> demand
        self.depot = depot_id
        self.optimal = optimal
        self.customers = [n for n in coords if n != depot_id]

    def dist(self, a, b):
        (x1, y1), (x2, y2) = self.coords[a], self.coords[b]
        return math.hypot(x2 - x1, y2 - y1)


def parse_vrp(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    def get_field(key):
        m = re.search(rf"{key}\s*:\s*(\S+)", text)
        return m.group(1) if m else None

    name = get_field("NAME")
    dimension = int(get_field("DIMENSION"))
    capacity = int(get_field("CAPACITY"))

    # จำนวนรถ (k) มักอยู่ใน COMMENT: "No of trucks: 5, Optimal value: 784"
    num_vehicles = None
    optimal = None
    m = re.search(r"No of trucks:\s*(\d+)", text)
    if m:
        num_vehicles = int(m.group(1))
    m = re.search(r"Optimal value:\s*(\d+)", text)
    if m:
        optimal = int(m.group(1))
    if num_vehicles is None:
        # fallback: เดาจากชื่อไฟล์ เช่น A-n32-k5
        m = re.search(r"-k(\d+)", name)
        num_vehicles = int(m.group(1)) if m else 5

    # NODE_COORD_SECTION
    coords = {}
    coord_block = re.search(r"NODE_COORD_SECTION\s*\n(.*?)DEMAND_SECTION", text, re.S).group(1)
    for line in coord_block.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3:
            node_id, x, y = int(parts[0]), float(parts[1]), float(parts[2])
            coords[node_id] = (x, y)

    # DEMAND_SECTION
    demands = {}
    demand_block = re.search(r"DEMAND_SECTION\s*\n(.*?)DEPOT_SECTION", text, re.S).group(1)
    for line in demand_block.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            node_id, d = int(parts[0]), int(parts[1])
            demands[node_id] = d

    # DEPOT_SECTION -> first id before -1
    depot_block = re.search(r"DEPOT_SECTION\s*\n(.*?)EOF", text, re.S).group(1)
    depot_id = None
    for line in depot_block.strip().splitlines():
        v = line.strip()
        if v and v != "-1":
            depot_id = int(v)
            break

    assert len(coords) == dimension, f"DIMENSION mismatch in {filepath}"

    return CVRPInstance(name, capacity, num_vehicles, coords, demands, depot_id, optimal)


if __name__ == "__main__":
    import glob
    for fp in glob.glob("data/*.vrp"):
        inst = parse_vrp(fp)
        print(f"{inst.name}: customers={len(inst.customers)}, k={inst.num_vehicles}, "
              f"Q={inst.capacity}, depot={inst.depot}, optimal={inst.optimal}")
