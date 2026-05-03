"""Merge all per-run campaign CSVs into a single labeled dataset.

Discovers every results_*.csv under the logs/ subdirectory (one level deep),
skips combined files and the dry_run folder, concatenates them, validates
schema, deduplicates, tags operating regime, adds a stratified train/val/test
split column, and writes merged_dataset.csv next to this script.

Usage:
    python merge_dataset.py
"""
import csv
import sys
from pathlib import Path
import statistics

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

SCRIPT_DIR = Path(__file__).parent
LOGS_DIR   = SCRIPT_DIR / "logs"
OUT_CSV    = SCRIPT_DIR / "merged_dataset.csv"

EXPECTED_COLS = [
    "campaign_id", "run_id", "timestamp_host",
    "rx_timestamp_ms", "tx_timestamp_ms", "inter_arrival_ms",
    "beacon_id", "seq_num", "pkt_type", "mod_kind", "spread_factor",
    "rssi_dbm", "snr_db", "freq_error_hz", "payload_len",
    "distance_m", "label_sf", "label_mod", "mod_kind_label",
    "label_beacon", "label_pkt",
]

SKIP_DIRS  = {"dry_run"}
SKIP_FILES = {"C1_combined.csv", "C2_combined.csv", "merged_dataset.csv"}


def discover_csvs():
    found = []
    for p in sorted(LOGS_DIR.rglob("results_*.csv")):
        if p.parent.name in SKIP_DIRS:
            continue
        if p.name in SKIP_FILES:
            continue
        found.append(p)
    return found


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def run_level_split(rows, label_col, fracs=(0.70, 0.15, 0.15), seed=42):
    """Stratified split keyed on run_id. The leakage-safe default.

    Fails to populate val/test when any label class has only 1-2 runs
    (the minority-class runs all land in train). Caller must check
    is_degenerate() and fall back to row_level_split() if so.
    """
    import random
    rng = random.Random(seed)
    from collections import defaultdict
    by_label = defaultdict(lambda: defaultdict(list))
    for i, row in enumerate(rows):
        by_label[row[label_col]][row["run_id"]].append(i)

    split_map = {}
    for label_val, run_dict in by_label.items():
        runs = sorted(run_dict.keys())
        rng.shuffle(runs)
        n = len(runs)
        n_train = max(1, round(n * fracs[0]))
        n_val   = max(1, round(n * fracs[1]))
        for j, run_id in enumerate(runs):
            if j < n_train:
                tag = "train"
            elif j < n_train + n_val:
                tag = "val"
            else:
                tag = "test"
            for idx in run_dict[run_id]:
                split_map[idx] = tag
    return split_map


def row_level_split(rows, label_col, fracs=(0.70, 0.15, 0.15), seed=42):
    """Row-level stratified split. Used when run-level stratification
    degenerates (any class has fewer than 3 runs).

    WARNING: this allows rows from the same run_id to appear in
    different splits, which means within-run channel state can leak
    across splits. The trade-off is acceptable when the alternative
    is a single-class val/test set, but any classifier output should
    be audited for session-signature artifacts (e.g. by checking
    that per-run accuracy is similar to global accuracy).
    """
    import random
    rng = random.Random(seed)
    from collections import defaultdict
    by_label = defaultdict(list)
    for i, row in enumerate(rows):
        by_label[row[label_col]].append(i)

    split_map = {}
    for label_val, idxs in by_label.items():
        idxs = list(idxs)
        rng.shuffle(idxs)
        n = len(idxs)
        n_train = max(1, round(n * fracs[0]))
        n_val   = max(1, round(n * fracs[1]))
        for j, idx in enumerate(idxs):
            if j < n_train:
                split_map[idx] = "train"
            elif j < n_train + n_val:
                split_map[idx] = "val"
            else:
                split_map[idx] = "test"
    return split_map


def is_degenerate(rows, split_map, label_cols):
    """A split is degenerate if any of the listed label columns has a
    class missing from val or test. Returns the list of (col, split,
    missing_classes) tuples; empty list means non-degenerate.
    """
    from collections import defaultdict
    issues = []
    for col in label_cols:
        by_split = defaultdict(set)
        all_classes = set()
        for i, row in enumerate(rows):
            cls = row[col]
            by_split[split_map.get(i, "train")].add(cls)
            all_classes.add(cls)
        for tag in ("val", "test"):
            missing = all_classes - by_split[tag]
            if missing:
                issues.append((col, tag, missing))
    return issues


def main():
    csvs = discover_csvs()
    if not csvs:
        print(f"No results_*.csv files found under {LOGS_DIR}")
        sys.exit(1)

    print(f"Found {len(csvs)} campaign CSV(s):\n")
    all_rows = []
    for p in csvs:
        rows = read_csv(p)
        if not rows:
            print(f"  [SKIP] {p.relative_to(SCRIPT_DIR)} - empty")
            continue
        missing = set(EXPECTED_COLS) - set(rows[0].keys())
        if missing:
            print(f"  [WARN] {p.name} missing columns: {missing}")
        cid = rows[0].get("campaign_id", "?")
        rid = rows[0].get("run_id", "?")
        print(f"  {p.relative_to(SCRIPT_DIR)}  ->  campaign={cid}  run={rid}  rows={len(rows)}")
        all_rows.extend(rows)

    print(f"\nTotal rows before dedup: {len(all_rows)}")

    # Dedup on (run_id, beacon_id, seq_num, pkt_type)
    seen = set()
    deduped = []
    for row in all_rows:
        key = (row.get("run_id"), row.get("beacon_id"),
               row.get("seq_num"), row.get("pkt_type"))
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    print(f"Total rows after dedup:  {len(deduped)}")

    # Tag regime
    for row in deduped:
        cid = row.get("campaign_id", "")
        row["regime"] = "contended" if cid.startswith("C5") else "clean"

    # Default: stratified run-level split keyed on label_sf (preserves
    # the run-level leakage guarantee). If that degenerates because any
    # downstream classification target has a class missing from val or
    # test, fall back to a row-level split with a loud warning.
    label_cols = ["label_sf", "label_beacon", "label_pkt"]
    split_map = run_level_split(deduped, "label_sf")
    issues = is_degenerate(deduped, split_map, label_cols)
    if issues:
        print(f"\n[WARN] Run-level split is degenerate ({len(issues)} issue(s)):")
        for col, tag, missing in issues:
            print(f"  {col} {tag}: missing classes {missing}")
        print("[WARN] Falling back to ROW-LEVEL stratified split keyed on")
        print("[WARN] label_sf. This violates the run-level leakage")
        print("[WARN] guarantee --- audit any classifier output for")
        print("[WARN] session-signature artifacts. Re-collect additional")
        print("[WARN] runs per minority class to restore run-level safety.")
        split_map = row_level_split(deduped, "label_sf")
        residual = is_degenerate(deduped, split_map, label_cols)
        if residual:
            print(f"[WARN] Row-level split still has {len(residual)} issue(s):")
            for col, tag, missing in residual:
                print(f"    {col} {tag}: missing {missing}")
        else:
            print("[INFO] Row-level split: every label class is present "
                  "in train, val, and test.")
    else:
        print("[INFO] Run-level split is non-degenerate (every label "
              "class is present in train, val, test).")
    for i, row in enumerate(deduped):
        row["split"] = split_map.get(i, "train")

    # Summary by campaign
    from collections import Counter
    by_campaign = Counter(r["campaign_id"] for r in deduped)
    by_regime   = Counter(r["regime"] for r in deduped)
    by_pkt      = Counter(r["pkt_type"] for r in deduped)
    by_split    = Counter(r["split"] for r in deduped)

    print("\n--- Summary ---")
    print("Rows per campaign_id:")
    for k, v in sorted(by_campaign.items()):
        print(f"  {k}: {v}")
    print(f"Regime:  {dict(by_regime)}")
    print(f"pkt_type: {dict(by_pkt)}")
    print(f"Split:   {dict(by_split)}")

    # Write output
    out_cols = EXPECTED_COLS + ["regime", "split"]
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deduped)

    print(f"\nSaved: {OUT_CSV}  ({len(deduped)} rows)")


if __name__ == "__main__":
    main()
