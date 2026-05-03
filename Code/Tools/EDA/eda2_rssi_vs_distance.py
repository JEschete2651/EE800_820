"""EDA 2 - RSSI vs. distance with FSPL overlay (Campaign C4).

If C4 data is absent from the merged dataset, prints a warning and exits.
Outputs eda2_rssi_vs_distance.png in this script's directory.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

MERGED = Path(__file__).parent.parent / "CampaignCollect" / "merged_dataset.csv"
OUT    = Path(__file__).parent / "eda2_rssi_vs_distance.png"

df = pd.read_csv(MERGED)
c4 = df[df["campaign_id"] == "C4"]

if c4.empty:
    print("[WARN] No C4 rows in merged_dataset.csv - C4 was not collected.")
    print("       Skipping eda2_rssi_vs_distance.png.")
    raise SystemExit(0)

means = c4.groupby("distance_m")["rssi_dbm"].mean()
stds  = c4.groupby("distance_m")["rssi_dbm"].std()

# FSPL model: RSSI(d) = P_tx - 20*log10(d) - 20*log10(f_Hz) + 147.55
f_hz    = 906.5e6
p_tx    = 14.0
d_range = np.linspace(0.5, 10, 300)
fspl    = p_tx - 20 * np.log10(d_range) - 20 * np.log10(f_hz) + 147.55

fig, ax = plt.subplots(figsize=(7, 4))
ax.errorbar(means.index, means.values, yerr=stds.values,
            fmt="o", capsize=5, color="steelblue", label="Measured mean RSSI")
ax.plot(d_range, fspl, "--", color="tomato",
        label="FSPL model (+14 dBm, 906.5 MHz)")
ax.set_xlabel("Distance (m)")
ax.set_ylabel("RSSI (dBm)")
ax.set_title("Campaign C4: RSSI vs. Distance with FSPL Overlay")
ax.legend()
plt.tight_layout()
plt.savefig(OUT, dpi=150)
print(f"Saved: {OUT}")
