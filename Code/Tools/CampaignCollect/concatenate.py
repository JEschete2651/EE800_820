"""Concatenate per-run CSVs from a Module 3 campaign into a single dataset.

Discovers campaigns from the JSON configs in ./campaigns, groups them by the
top-level `campaign_id` field, and lists each campaign with how many of its
configured sweep points have a log on disk under ./logs/<config-stem>/. The
user picks a campaign; the script concatenates every available per-run CSV,
prints a per-run_id summary, and writes a combined CSV to
./logs/<campaign_id>_combined.csv.

Stdlib only (csv, json, statistics, pathlib) to match collect.py.

Usage:
    python concatenate.py
    (interactive menu)
"""
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR    = Path(__file__).parent
CAMPAIGNS_DIR = SCRIPT_DIR / "campaigns"
LOGS_DIR      = SCRIPT_DIR / "logs"


def _load_configs():
    """Return list of (config_path, cfg_dict). Skips invalid JSON."""
    out = []
    for p in sorted(CAMPAIGNS_DIR.glob("*.json")):
        try:
            with open(p) as f:
                out.append((p, json.load(f)))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [WARN] Could not read {p.name}: {e}")
    return out


def _group_by_campaign(configs):
    """Group configs by campaign_id. Returns dict campaign_id -> list of (path, cfg)."""
    groups = defaultdict(list)
    for path, cfg in configs:
        cid = cfg.get("campaign_id", "UNKNOWN")
        groups[cid].append((path, cfg))
    return dict(sorted(groups.items()))


def _csv_for_config(config_path):
    """Path to the CSV produced by collect.py for this config (may not exist)."""
    return LOGS_DIR / config_path.stem / f"results_{config_path.stem}.csv"


def _summarize_campaign(campaign_id, entries):
    """Return (n_configs, n_with_log, total_rows_if_known)."""
    n_with_log = 0
    total_rows = 0
    for path, _cfg in entries:
        csv_path = _csv_for_config(path)
        if csv_path.exists():
            n_with_log += 1
            with open(csv_path) as f:
                total_rows += sum(1 for _ in f) - 1  # minus header
    return len(entries), n_with_log, total_rows


def _menu(groups):
    print("\n=== Campaign Concatenate ===")
    print("Available campaigns:\n")
    keys = list(groups.keys())
    for i, cid in enumerate(keys, 1):
        n, n_log, rows = _summarize_campaign(cid, groups[cid])
        sweep_var = groups[cid][0][1].get("sweep_variable", "?")
        if n_log == 0:
            status = "no logs yet"
        elif n_log == n:
            status = "complete"
        else:
            status = f"partial ({n_log}/{n})"
        print(f"  {i:2d}.  {cid}  ({sweep_var} sweep, {n} points)")
        print(f"       Logs on disk: {n_log}/{n} — {status} — {rows} total rows")
    print()

    while True:
        try:
            choice = input("Select campaign number: ").strip()
        except EOFError:
            print("\n  No input received.")
            sys.exit(1)
        try:
            idx = int(choice) - 1
        except ValueError:
            print("  Invalid input.")
            continue
        if 0 <= idx < len(keys):
            return keys[idx]
        print(f"  Enter a number between 1 and {len(keys)}.")


def _read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _concat(entries):
    """Read every available CSV. Returns (rows, header, missing_configs)."""
    rows = []
    header = None
    missing = []
    for path, cfg in entries:
        csv_path = _csv_for_config(path)
        if not csv_path.exists():
            missing.append((path.stem, cfg.get("description", path.stem)))
            continue
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            if header is None:
                header = reader.fieldnames
            elif reader.fieldnames != header:
                print(f"  [WARN] Schema mismatch in {csv_path.name}; "
                      f"expected {header}, got {reader.fieldnames}")
            rows.extend(reader)
    return rows, header, missing


def _safe_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _agg(values):
    """Mean/std/min/max for a list of floats. Returns dict or None if empty."""
    vs = [v for v in values if v is not None]
    if not vs:
        return None
    return {
        "n":    len(vs),
        "mean": statistics.mean(vs),
        "std":  statistics.stdev(vs) if len(vs) > 1 else 0.0,
        "min":  min(vs),
        "max":  max(vs),
    }


def _print_summary(rows, sweep_variable):
    print(f"\nTotal rows: {len(rows)}")
    if not rows:
        return

    # Group by run_id, but order by sweep value so the table reads in sweep order.
    groups = defaultdict(list)
    sweep_for_run = {}
    for r in rows:
        rid = r["run_id"]
        groups[rid].append(r)
        # Pick a representative sweep value from the row. For tx_power that's the
        # campaign's `sweep_value`, which we don't have here; fall back to the
        # column most likely to vary along the sweep axis.
        if rid not in sweep_for_run:
            sweep_for_run[rid] = (r.get("spread_factor"), r.get("payload_len"))

    print()
    print(f"Per-run summary (sweep variable: {sweep_variable}):")
    print(f"  {'run_id':<40} {'n':>4} "
          f"{'rssi_mean':>10} {'rssi_std':>9} "
          f"{'snr_mean':>9} {'ia_mean_ms':>11}")

    for rid in sorted(groups):
        rs = groups[rid]
        rssi = _agg([_safe_float(r["rssi_dbm"])      for r in rs])
        snr  = _agg([_safe_float(r["snr_db"])        for r in rs])
        ia   = _agg([_safe_float(r["inter_arrival_ms"])
                     for r in rs if _safe_float(r["inter_arrival_ms"]) not in (None, 0.0)])

        rssi_str = f"{rssi['mean']:>10.2f}" if rssi else f"{'--':>10}"
        rssi_sd  = f"{rssi['std']:>9.2f}"   if rssi else f"{'--':>9}"
        snr_str  = f"{snr['mean']:>9.2f}"   if snr  else f"{'--':>9}"
        ia_str   = f"{ia['mean']:>11.2f}"   if ia   else f"{'--':>11}"
        print(f"  {rid:<40} {len(rs):>4} {rssi_str} {rssi_sd} {snr_str} {ia_str}")


def main():
    if not CAMPAIGNS_DIR.is_dir():
        print(f"Campaigns directory not found: {CAMPAIGNS_DIR}")
        sys.exit(1)

    configs = _load_configs()
    if not configs:
        print("No campaign JSON configs found.")
        sys.exit(1)

    groups = _group_by_campaign(configs)
    campaign_id = _menu(groups)
    entries = groups[campaign_id]

    rows, header, missing = _concat(entries)

    if missing:
        print("\nMissing per-run logs (these sweep points have no CSV yet):")
        for stem, desc in missing:
            print(f"  - {stem} : {desc}")
        if not rows:
            print("\nNothing to concatenate.")
            sys.exit(1)
        ans = input("\nProceed with the available logs? [Y/n]: ").strip().lower()
        if ans == "n":
            sys.exit(0)

    sweep_variable = entries[0][1].get("sweep_variable", "?")
    _print_summary(rows, sweep_variable)

    out_path = LOGS_DIR / f"{campaign_id}_combined.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote combined CSV: {out_path}")


if __name__ == "__main__":
    main()
