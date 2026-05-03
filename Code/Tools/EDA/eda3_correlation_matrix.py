"""EDA 3 - Feature correlation matrix (full dataset).

Outputs eda3_correlation_matrix.png in this script's directory.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

MERGED = Path(__file__).parent.parent / "CampaignCollect" / "merged_dataset.csv"
OUT    = Path(__file__).parent / "eda3_correlation_matrix.png"

df = pd.read_csv(MERGED)

numeric_cols = ["rssi_dbm", "snr_db", "inter_arrival_ms",
                "freq_error_hz", "spread_factor", "distance_m"]
corr = df[numeric_cols].astype(float).corr()

fig, ax = plt.subplots(figsize=(7, 6))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
            square=True, linewidths=0.5, ax=ax)
ax.set_title("Feature Correlation Matrix (Full Dataset)")
plt.tight_layout()
plt.savefig(OUT, dpi=150)
print(f"Saved: {OUT}")

# Print pairs with |r| > 0.7
print("\nStrongly correlated pairs (|r| > 0.7):")
found = False
for i, c1 in enumerate(numeric_cols):
    for c2 in numeric_cols[i+1:]:
        r = corr.loc[c1, c2]
        if abs(r) > 0.7:
            print(f"  {c1} <-> {c2}: r = {r:.3f}")
            found = True
if not found:
    print("  None")
