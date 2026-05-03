"""EDA 1 - RSSI distribution by TX power (Campaign C1).

Reads merged_dataset.csv from the CampaignCollect folder.
Outputs eda1_rssi_by_txpower.png in this script's directory.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

MERGED = Path(__file__).parent.parent / "CampaignCollect" / "merged_dataset.csv"
OUT    = Path(__file__).parent / "eda1_rssi_by_txpower.png"

df = pd.read_csv(MERGED)
c1 = df[df["campaign_id"] == "C1"].copy()
c1["tx_power"] = c1["run_id"].str.extract(r"pwr(\d+)").astype(int)
c1 = c1.sort_values("tx_power")

fig, ax = plt.subplots(figsize=(7, 4))
sns.violinplot(data=c1, x="tx_power", y="rssi_dbm", ax=ax,
               inner="box", cut=0, color="steelblue")
ax.set_xlabel("TX Power (dBm)")
ax.set_ylabel("RSSI (dBm)")
ax.set_title("Campaign C1: RSSI Distribution by TX Power")

# Annotate means
for i, pwr in enumerate(sorted(c1["tx_power"].unique())):
    mean = c1[c1["tx_power"] == pwr]["rssi_dbm"].mean()
    ax.text(i, mean + 0.4, f"{mean:.1f}", ha="center", va="bottom",
            fontsize=8, color="white", fontweight="bold")

plt.tight_layout()
plt.savefig(OUT, dpi=150)
print(f"Saved: {OUT}")
