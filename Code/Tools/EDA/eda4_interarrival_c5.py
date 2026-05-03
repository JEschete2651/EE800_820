"""EDA 4 - Inter-arrival time distribution: C5a vs. C5b.

Outputs eda4_interarrival_scheduling.png in this script's directory.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

MERGED = Path(__file__).parent.parent / "CampaignCollect" / "merged_dataset.csv"
OUT    = Path(__file__).parent / "eda4_interarrival_scheduling.png"

df = pd.read_csv(MERGED)

# Both sub-configs share campaign_id="C5"; distinguish by run_id prefix.
c5a = df[df["run_id"].str.startswith("C5a")]["inter_arrival_ms"].astype(float)
c5b = df[df["run_id"].str.startswith("C5b")]["inter_arrival_ms"].astype(float)

# Drop the first-row zero (join-mid-stream artifact)
c5a = c5a[c5a > 0]
c5b = c5b[c5b > 0]

fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(c5a, bins=40, alpha=0.65, color="steelblue",
        label=f"C5a - single station DATA-only (n={len(c5a)})")
ax.hist(c5b, bins=40, alpha=0.65, color="tomato",
        label=f"C5b - ping-pong DATA+ACK (n={len(c5b)})")
ax.set_xlabel("Inter-arrival Time (ms)")
ax.set_ylabel("Count")
ax.set_title("Inter-arrival Time: C5a Single Station vs. C5b Ping-pong")
ax.legend()
plt.tight_layout()
plt.savefig(OUT, dpi=150)
print(f"Saved: {OUT}")

print(f"\nC5a IA: mean={c5a.mean():.1f} ms  std={c5a.std():.1f} ms")
print(f"C5b IA: mean={c5b.mean():.1f} ms  std={c5b.std():.1f} ms")
