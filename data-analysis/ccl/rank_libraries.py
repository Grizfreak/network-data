"""Rank the four networking libraries by overall win rate per platform."""
import pandas as pd

df = pd.read_csv("analysis_results/statistical_comparisons.csv")
LIBS = ["Photon", "NGO", "FishNet", "NetcodeEntities"]

# Keep only cross-library pairs (drop the "Other" / "Base*" rows).
mask = df["A_subsystem"].isin(LIBS) & df["B_subsystem"].isin(LIBS)
df = df[mask].copy()


def _winners(row):
    """From a verdict like 'A better (lower)' or 'B better (higher)' return
    the set of winning subsystem names. Returns an empty set if not significant
    or the verdict is non-directional."""
    if row["p_value"] >= 0.05:
        return set()
    v = str(row["verdict"])
    if v == "no significant difference":
        return set()
    if v.startswith("A "):
        return {row["A_subsystem"]}
    if v.startswith("B "):
        return {row["B_subsystem"]}
    return set()


# For each row, add the winner(s)
df["winners"] = df.apply(_winners, axis=1)

# A pair is "decisive" if p<0.05 AND effect size is at least small.
df["decisive"] = (df["p_value"] < 0.05) & (df["effect_size"].isin(["small", "medium", "large"]))

# Build win counts per library per platform per metric, weighting by effect size.
WEIGHT = {"large": 3.0, "medium": 2.0, "small": 1.0, "negligible": 0.0}
df["weight"] = df["effect_size"].map(WEIGHT).fillna(0.0)

# Expand winners into long format
long = []
for _, r in df.iterrows():
    if not r["decisive"]:
        continue
    for w in r["winners"]:
        long.append({
            "platform": r["platform"],
            "metric": r["metric"],
            "winner": w,
            "loser": (r["B_subsystem"] if w == r["A_subsystem"] else r["A_subsystem"]),
            "weight": r["weight"],
            "delta": r["cliffs_delta"],
            "p_value": r["p_value"],
        })
wins = pd.DataFrame(long)

print("Decisive cross-library wins (small+ effect, p<0.05):\n")
for platform in ["PC", "Quest"]:
    sub = wins[wins["platform"] == platform]
    if sub.empty:
        continue
    print(f"=== {platform} ===")
    pivot = (
        sub.groupby(["metric", "winner"])["weight"].sum()
        .unstack(fill_value=0.0)
    )
    # ensure all libs in columns
    for lib in LIBS:
        if lib not in pivot.columns:
            pivot[lib] = 0.0
    pivot = pivot[LIBS]
    print(pivot.round(1).to_string())
    print()

print("Overall weighted wins per library:\n")
for platform in ["PC", "Quest"]:
    sub = wins[wins["platform"] == platform]
    if sub.empty:
        continue
    total = sub.groupby("winner")["weight"].sum().reindex(LIBS, fill_value=0.0)
    total = total.sort_values(ascending=False)
    print(f"  {platform}:")
    for lib, score in total.items():
        print(f"    {lib:18s}  weighted-wins = {score:5.1f}")
    print()
