
import os, yaml, numpy as np, pandas as pd
import pypsa

CONFIG = yaml.safe_load(open("config/config.yaml", "r")) if os.path.exists("config/config.yaml") else yaml.safe_load(open("config/config.example.yaml","r"))
np.random.seed(CONFIG.get("random_seed", 42))

def build_synthetic():
    n = pypsa.Network()
    # Ensure a default carrier exists for power components
    if "AC" not in n.carriers.index:
        n.add("Carrier", "AC")

    hours = pd.date_range("2025-01-01", periods=168, freq="H")
    n.set_snapshots(hours)

    buses = [
        ("BENGALURU_220kV", "IN-SK"),
        ("HYDERABAD_220kV", "IN-TS"),
        ("CHENNAI_220kV", "IN-TN"),
        ("PUNE_220kV", "IN-MH"),
        ("NOIDA_220kV", "IN-UP"),
        ("MUMBAI_220kV", "IN-MH"),
        ("AHMEDABAD_220kV", "IN-GJ"),
        ("KOLKATA_220kV", "IN-WB"),
    ]
    for b, c in buses:
        # Explicitly set a carrier so newer PyPSA versions pass consistency checks
        n.add("Bus", b, country=c, carrier="AC")

    def line(a,b,s=1000):
        n.add("Line", f"{a}__{b}", bus0=a, bus1=b, x=0.0001, r=0.00001, s_nom=s, carrier="AC")

    ring = ["BENGALURU_220kV","CHENNAI_220kV","KOLKATA_220kV","NOIDA_220kV","AHMEDABAD_220kV","MUMBAI_220kV","PUNE_220kV","HYDERABAD_220kV"]
    for i in range(len(ring)):
        line(ring[i], ring[(i+1)%len(ring)], s=1500)

    line("BENGALURU_220kV","HYDERABAD_220kV",s=1200)
    line("PUNE_220kV","AHMEDABAD_220kV",s=1200)
    line("MUMBAI_220kV","NOIDA_220kV",s=1200)
    line("CHENNAI_220kV","NOIDA_220kV",s=1000)

    base_MW = {
        "BENGALURU_220kV": 3000,
        "HYDERABAD_220kV": 2500,
        "CHENNAI_220kV": 2800,
        "PUNE_220kV": 2600,
        "NOIDA_220kV": 3200,
        "MUMBAI_220kV": 3500,
        "AHMEDABAD_220kV": 2200,
        "KOLKATA_220kV": 3000,
    }
    diurnal = (1.0 + 0.15*np.sin(np.arange(len(hours))/24*2*np.pi))
    for b, base in base_MW.items():
        series = pd.Series(base*diurnal, index=hours)
        n.add("Load", f"native_{b}", bus=b, p_set=series, carrier="AC")

    # Carriers with CO2 intensities (tCO2/MWh)
    for carr, ef in [("coal",0.95),("gas",0.40),("oil",0.78),("solar",0.0),("wind",0.0)]:
        if carr not in n.carriers.index:
            n.add("Carrier", carr, co2_emissions=ef)
        else:
            n.carriers.loc[carr,"co2_emissions"] = ef

    # Thermal generators
    gen_specs = [("coal", 8000, 28.0), ("gas", 5000, 55.0)]
    for carrier, cap, mc in gen_specs:
        for b in base_MW.keys():
            n.add(
                "Generator",
                f"{carrier}_{b}",
                bus=b,
                p_nom=cap/len(base_MW),
                marginal_cost=mc,
                carrier=carrier,
                p_max_pu=1.0,
                p_nom_extendable=True,
                capital_cost=0.0,
            )

    # Renewables
    rng = np.random.default_rng(0)
    hours_index = pd.Index(range(len(hours)))
    solar_profile = pd.Series([max(0.0, np.sin((h%24 - 6)/12*np.pi)) for h in hours_index], index=hours)
    wind_profile = pd.Series(0.5 + 0.3*rng.standard_normal(len(hours)), index=hours).clip(0,1)

    for b in base_MW.keys():
        n.add(
            "Generator",
            f"solar_{b}",
            bus=b,
            p_nom=1500,
            carrier="solar",
            marginal_cost=0.0,
            p_max_pu=solar_profile.values,
            p_nom_extendable=True,
            capital_cost=0.0,
        )
        n.add(
            "Generator",
            f"wind_{b}",
            bus=b,
            p_nom=1000,
            carrier="wind",
            marginal_cost=0.0,
            p_max_pu=wind_profile.values,
            p_nom_extendable=True,
            capital_cost=0.0,
        )

    # Storage
    for b in base_MW.keys():
        n.add("Store", f"bat_e_{b}", bus=b, e_nom=500, e_cyclic=True, standing_loss=0.0005, carrier="AC")
        n.add("Link", f"bat_p_{b}", bus0=b, bus1=b, p_nom=500, efficiency=0.96, carrier="AC")

    os.makedirs("data/built", exist_ok=True)
    n.export_to_netcdf("data/built/synthetic_india.nc")
    return "data/built/synthetic_india.nc"

def main():
    network_path = CONFIG.get("network_path","data/input/india.nc")
    use_synth = CONFIG.get("use_synthetic_if_missing", True)

    if os.path.exists(network_path):
        print(f"Using provided network at {network_path}")
        n = pypsa.Network(network_path)
        n.export_to_netcdf("data/built/base.nc")
        print("Copied to data/built/base.nc")
    elif use_synth:
        print("No provided network found; building a synthetic India network...")
        synth = build_synthetic()
        os.replace(synth, "data/built/base.nc")
        print("Synthetic network at data/built/base.nc")
    else:
        raise FileNotFoundError(f"Network not found at {network_path} and use_synthetic_if_missing=False")

if __name__ == "__main__":
    main()
