"""Render the cross-library subset of the statistical comparisons."""
import pandas as pd

df = pd.read_csv("analysis_results/statistical_comparisons_significant.csv")
libs = ["Photon", "NGO", "FishNet", "NetcodeEntities"]
mask = df["A_subsystem"].isin(libs) & df["B_subsystem"].isin(libs)
sub = df[mask].copy()

# Count "wins" per library per metric / platform
print("Cross-library significant pairs (Photon / NGO / FishNet / NetcodeEntities):\n")
for metric in sorted(sub["metric"].unique()):
    print(f"=== {metric} ===")
    rows = sub[sub["metric"] == metric]
    for platform in ["PC", "Quest"]:
        plat = rows[rows["platform"] == platform]
        if plat.empty:
            continue
        print(f"  {platform}:")
        for _, r in plat.iterrows():
            a = r["A_subsystem"]
            b = r["B_subsystem"]
            med_a = r["median_A"]
            med_b = r["median_B"]
            unit = r["unit"]
            p = r["p_value"]
            d = r["cliffs_delta"]
            es = r["effect_size"]
            verdict = r["verdict"]
            print(
                f"    {a:18s} vs {b:18s} med_A={med_a:>10.3f} med_B={med_b:>10.3f} "
                f"{unit:8s} p={p:.2e} delta={d:+.3f} ({es}) => {verdict}"
            )
    print()
