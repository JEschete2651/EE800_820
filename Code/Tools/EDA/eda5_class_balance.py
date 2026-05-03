"""EDA 5 - Class balance across all four classification tasks.

Outputs eda5_class_balance.png in this script's directory.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

MERGED = Path(__file__).parent.parent / "CampaignCollect" / "merged_dataset.csv"
OUT    = Path(__file__).parent / "eda5_class_balance.png"

df = pd.read_csv(MERGED)

TASKS = [
    ("label_sf",     "Spreading Factor",  str),
    ("label_mod",    "Modulation",        str),
    ("label_beacon", "Beacon ID",         str),
    ("label_pkt",    "Packet Type",       lambda x: {0: "DATA", 1: "ACK"}.get(int(x), str(x))),
]

fig, axes = plt.subplots(1, 4, figsize=(14, 4))

for ax, (col, title, fmt) in zip(axes, TASKS):
    counts = df[col].value_counts().sort_index()
    labels = [fmt(k) for k in counts.index]
    bars = ax.bar(labels, counts.values, color="steelblue", edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(col)
    ax.set_ylabel("Count")
    # Annotate bar heights
    for bar, v in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                str(v), ha="center", va="bottom", fontsize=8)
    # Flag thin classes
    threshold = 150
    for bar, v in zip(bars, counts.values):
        if v < threshold:
            bar.set_color("tomato")

fig.suptitle("Class Balance — All Four Classification Tasks", fontsize=12)
plt.tight_layout()
plt.savefig(OUT, dpi=150)
print(f"Saved: {OUT}")

print("\nClass counts (red bars = < 150 samples):")
for col, title, fmt in TASKS:
    counts = df[col].value_counts().sort_index()
    print(f"\n  {title} ({col}):")
    for k, v in counts.items():
        flag = " <-- LOW" if v < 150 else ""
        print(f"    {fmt(k)}: {v}{flag}")
