
import os, pandas as pd, matplotlib.pyplot as plt

os.makedirs("data/results/plots", exist_ok=True)

kpis = pd.read_csv("data/results/kpis.csv", index_col=0, header=None).squeeze("columns")
plt.figure()
kpis.plot(kind="bar")
plt.title("System KPIs")
plt.ylabel("Value (native units)")
plt.tight_layout()
plt.savefig("data/results/plots/kpis.png", dpi=200)
plt.close()

ci = pd.read_csv("data/results/avg_carbon_intensity_bus_hour.csv", index_col=0, parse_dates=True)
ci_mean = ci.mean(axis=0).sort_values()
plt.figure()
ci_mean.plot(kind="bar")
plt.title("Average Carbon Intensity by Bus")
plt.ylabel("tCO2 / MWh")
plt.tight_layout()
plt.savefig("data/results/plots/avg_ci_by_bus.png", dpi=200)
plt.close()

print("Plots saved to data/results/plots/")
