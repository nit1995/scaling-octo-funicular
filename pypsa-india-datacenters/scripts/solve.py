
import os, yaml, pandas as pd, numpy as np
import pypsa

CONFIG = yaml.safe_load(open("config/config.yaml", "r")) if os.path.exists("config/config.yaml") else yaml.safe_load(open("config/config.example.yaml","r"))
SITES  = yaml.safe_load(open("scenarios/sites.yaml","r"))

def find_bus(n, key):
    key = key.lower()
    for b in n.buses.index:
        if key in b.lower():
            return b
    return n.buses.index[0]

def add_dc_loads(n: pypsa.Network):
    for s in SITES["sites"]:
        bus = find_bus(n, s["bus_contains"])
        base = s["peak_MW"] * s["load_factor"]
        series = pd.Series(base * s["PUE"], index=n.snapshots)
        n.add("Load", s["name"], bus=bus, p_set=series)

        if s.get("onsite",{}).get("pv", False):
            if "p_max_pu" in n.generators_t and len(n.generators_t.p_max_pu.columns)>0:
                ref = n.generators_t.p_max_pu.columns[0]
                p_max = n.generators_t.p_max_pu[ref]
            else:
                p_max = pd.Series(0.5, index=n.snapshots)
            n.add("Generator", f"{s['name']}_PV", bus=bus, carrier="solar", p_nom_extendable=True,
                  capital_cost=500e3, marginal_cost=0.0, p_max_pu=p_max.values)

        if s.get("onsite",{}).get("battery", False):
            n.add("Store", f"{s['name']}_BAT_E", bus=bus, e_nom_extendable=True,
                  capital_cost=120e3, e_cyclic=True, standing_loss=0.0005)
            n.add("Link", f"{s['name']}_BAT_P", bus0=bus, bus1=bus, p_nom_extendable=True,
                  efficiency=0.96)

def set_co2_cap(n: pypsa.Network):
    if "co2_emissions" not in n.carriers.columns:
        n.carriers["co2_emissions"] = 0.0
    n.carriers["co2_emissions"] = n.carriers["co2_emissions"].fillna(0.0)

    cap = CONFIG.get("co2_cap_tco2", 1e12)
    if "CO2Limit" not in n.global_constraints.index:
        n.add("GlobalConstraint","CO2Limit", type="primary_energy", carrier_attribute="co2_emissions",
              sense="<=", constant=cap)

def average_carbon_intensity(n: pypsa.Network) -> pd.DataFrame:
    ef = n.carriers["co2_emissions"].fillna(0.0).to_dict()

    gen = n.generators.copy()
    gen_out = n.generators_t.p.copy()
    gen_out.columns = gen.index
    gen_bus = gen.bus.to_dict()
    gen_carrier = gen.carrier.to_dict()

    load = n.loads.copy()
    load_p = n.loads_t.p.copy()
    load_p.columns = load.index
    load_bus = load.bus.to_dict()

    buses = n.buses.index
    idx = n.snapshots

    emis = pd.DataFrame(0.0, index=idx, columns=buses)
    demand = pd.DataFrame(0.0, index=idx, columns=buses)

    for g in gen.index:
        b = gen_bus[g]
        c = gen_carrier[g]
        emis[b] += gen_out[g]*ef.get(c,0.0)

    for ld in load.index:
        b = load_bus[ld]
        demand[b] += load_p[ld].clip(lower=0.0)

    ci = emis.divide(demand.replace(0, np.nan))
    return ci

def marginal_carbon_intensity_via_dual(n: pypsa.Network) -> pd.Series:
    if "CO2Limit" in n.global_constraints.index:
        return pd.Series({"co2_shadow_price": n.global_constraints.loc["CO2Limit","mu"]})
    else:
        return pd.Series({"co2_shadow_price": 0.0})

def main():
    os.makedirs("data/results", exist_ok=True)
    n = pypsa.Network("data/built/base.nc")

    add_dc_loads(n)
    set_co2_cap(n)

    solver = CONFIG.get("solver","highs")
    status, condition = n.optimize(solver_name=solver)
    if status != "ok" or condition != "optimal":
        raise RuntimeError(f"Optimization failed: {status} ({condition})")

    system_cost = n.objective
    # Loads are stored as negative injections; flip sign for total demand
    load_sum = -n.loads_t.p.sum().sum()
    lcoe = system_cost / max(load_sum, 1e-6)

    ci = average_carbon_intensity(n)
    ci.to_csv("data/results/avg_carbon_intensity_bus_hour.csv")

    mci = marginal_carbon_intensity_via_dual(n)
    mci.to_csv("data/results/marginal_co2_shadow_price.csv")

    pd.Series({"system_cost": system_cost, "lcoe": lcoe}).to_csv("data/results/kpis.csv")
    n.export_to_netcdf("data/results/solved.nc")

    print("Solved. KPIs and CI written to data/results/.")

if __name__ == "__main__":
    main()
