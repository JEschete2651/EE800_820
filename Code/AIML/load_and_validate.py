"""LH4-A - Dataset loading, schema validation, and 9-check audit.

Reads merged_dataset.csv from Code/Tools/CampaignCollect/, runs the
nine-check audit, writes validation_manifest.json next to this script,
and emits a timestamped log to Code/AIML/Logs/.

Run:
    python load_and_validate.py
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
MERGED_CSV    = SCRIPT_DIR.parent / "Tools" / "CampaignCollect" / "merged_dataset.csv"
MANIFEST_PATH = SCRIPT_DIR / "validation_manifest.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"load_and_validate_{run_stamp}.log"
log_latest  = LOG_DIR / "load_and_validate_latest.log"

log = logging.getLogger("validate")
log.setLevel(logging.DEBUG)
log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for handler in (logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
                logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    handler.setFormatter(fmt)
    log.addHandler(handler)

log.info("=== load_and_validate.py starting ===")
log.info(f"Run stamp: {run_stamp}")
log.info(f"Source CSV: {MERGED_CSV}")
log.info(f"Archive log: {log_archive}")


# 23-column schema produced by Module 3's merge_dataset.py (LH3-H).
EXPECTED_COLS = [
    "campaign_id", "run_id", "timestamp_host",
    "rx_timestamp_ms", "tx_timestamp_ms", "inter_arrival_ms",
    "beacon_id", "seq_num", "pkt_type", "mod_kind", "spread_factor",
    "rssi_dbm", "snr_db", "freq_error_hz", "payload_len",
    "distance_m", "label_sf", "label_mod", "mod_kind_label",
    "label_beacon", "label_pkt", "regime", "split",
]

VALID_MOD_KINDS = {1, 2, 3}
VALID_PKT_TYPES = {0, 1}
PKT_TYPE_DATA, PKT_TYPE_ACK = 0, 1
VALID_REGIMES = {"clean", "contended"}
EXPECTED_CAMPAIGN_IDS = {"C1", "C2", "C4", "C5"}


if not MERGED_CSV.exists():
    log.error(f"merged_dataset.csv not found at {MERGED_CSV}")
    log.error("Run Code/Tools/CampaignCollect/merge_dataset.py first.")
    sys.exit(1)

df = pd.read_csv(MERGED_CSV)
log.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")


def check_1_schema(df):
    missing = set(EXPECTED_COLS) - set(df.columns)
    extra   = set(df.columns) - set(EXPECTED_COLS)
    if missing:
        raise AssertionError(f"Missing columns: {missing}")
    if extra:
        log.info(f"Extra columns present (not fatal): {extra}")


def check_2_row_count(df, min_rows=2100):
    if len(df) < min_rows:
        raise AssertionError(
            f"Row count {len(df)} < expected minimum {min_rows}")
    log.debug(f"Row count {len(df)} meets minimum {min_rows}")


def check_3_nulls(df, budget_frac=0.01):
    frac = df.isna().mean()
    over = frac[frac > budget_frac]
    if not over.empty:
        raise AssertionError(f"Columns over null budget: {over.to_dict()}")


def check_4_duplicates(df):
    key = ["run_id", "beacon_id", "seq_num", "pkt_type"]
    dup = df.duplicated(subset=key).sum()
    if dup:
        raise AssertionError(f"{dup} duplicate {tuple(key)} rows")


def check_5_valid_ranges(df):
    if not df["rssi_dbm"].between(-120, 0).all():
        raise AssertionError("rssi_dbm out of range")
    if not df["snr_db"].between(-20, 15).all():
        raise AssertionError("snr_db out of range")
    if not df["label_sf"].between(7, 10).all():
        raise AssertionError("label_sf out of range")
    if not set(df["beacon_id"].unique()) <= {1, 2, 255}:
        raise AssertionError(
            "beacon_id contains non-canonical values (expected {1, 2, 255})")
    bad = set(df["mod_kind"].unique()) - VALID_MOD_KINDS
    if bad:
        raise AssertionError(f"mod_kind non-canonical: {bad}")
    bad = set(df["mod_kind_label"].unique()) - VALID_MOD_KINDS
    if bad:
        raise AssertionError(f"mod_kind_label non-canonical: {bad}")
    bad = set(df["pkt_type"].unique()) - VALID_PKT_TYPES
    if bad:
        raise AssertionError(f"pkt_type non-canonical: {bad}")
    bad = set(df["regime"].unique()) - VALID_REGIMES
    if bad:
        raise AssertionError(f"regime non-canonical: {bad}")
    unknown = set(df["campaign_id"].unique()) - EXPECTED_CAMPAIGN_IDS
    if unknown:
        log.info(f"Non-standard campaign_id values: {unknown}")


def check_6_rssi_sign(df):
    if df["rssi_dbm"].max() > 0:
        raise AssertionError(
            f"rssi_dbm contains positive values (max={df['rssi_dbm'].max()}); "
            "column was corrupted upstream")


def check_7_label_consistency(df, threshold=0.02):
    data = df[df["pkt_type"] == PKT_TYPE_DATA]
    if data.empty:
        log.warning("No DATA rows present; skipping label-consistency check.")
        return
    sf_mismatch  = (data["spread_factor"] != data["label_sf"])
    mod_mismatch = (data["mod_kind"]      != data["mod_kind_label"])
    rate = (sf_mismatch | mod_mismatch).mean()
    log.debug(f"DATA label mismatch rate: {rate:.2%} "
              f"(sf={sf_mismatch.sum()}, mod={mod_mismatch.sum()})")
    if rate >= threshold:
        raise AssertionError(
            f"DATA-row label mismatch rate {rate:.1%} >= {threshold:.0%}")


def check_8_class_balance(df, min_per_class=150):
    for col in ["label_sf", "label_mod", "label_beacon", "label_pkt"]:
        counts = df[col].value_counts()
        small = counts[counts < min_per_class]
        if not small.empty:
            log.warning(f"{col} classes under {min_per_class}: "
                        f"{small.to_dict()}")


def check_9_split_integrity(df):
    leak = (df.groupby("run_id")["split"].nunique() > 1)
    leaked = leak[leak].index.tolist()
    if leaked:
        raise AssertionError(f"Run IDs split across partitions: {leaked}")


CHECKS = [
    check_1_schema, check_2_row_count, check_3_nulls,
    check_4_duplicates, check_5_valid_ranges, check_6_rssi_sign,
    check_7_label_consistency, check_8_class_balance, check_9_split_integrity,
]

failed = []
for fn in CHECKS:
    try:
        fn(df)
        log.info(f"[PASS] {fn.__name__}")
    except AssertionError as e:
        log.error(f"[FAIL] {fn.__name__}: {e}")
        failed.append(fn.__name__)

if failed:
    log.error(f"{len(failed)} check(s) failed: {failed}")
    sys.exit(1)
log.info(f"All {len(CHECKS)} checks passed.")


data_mask = df["pkt_type"] == PKT_TYPE_DATA
n_mismatch = int(
    ((df.loc[data_mask, "spread_factor"] != df.loc[data_mask, "label_sf"]) |
     (df.loc[data_mask, "mod_kind"]      != df.loc[data_mask, "mod_kind_label"]))
    .sum()
)

log.info("=== Dataset Summary ===")
log.info(f"Total rows:          {len(df):,}")
log.info(f"Unique campaigns:    {df['campaign_id'].nunique()}")
log.info(f"Unique runs:         {df['run_id'].nunique()}")
log.info(f"Regimes:             {df['regime'].value_counts().to_dict()}")
log.info(f"Splits:              {df['split'].value_counts().to_dict()}")
log.info(f"SF classes:          {df['label_sf'].value_counts().sort_index().to_dict()}")
log.info(f"Mod classes:         {df['label_mod'].value_counts().to_dict()}")
log.info(f"Beacon classes:      {df['label_beacon'].value_counts().sort_index().to_dict()}")
log.info(f"Pkt-type classes:    {df['label_pkt'].value_counts().sort_index().to_dict()}")
log.info(f"DATA-row mismatches: {n_mismatch}")


manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_stamp":    run_stamp,
    "source_file":  str(MERGED_CSV),
    "log_archive":  str(log_archive),
    "row_count":    int(len(df)),
    "schema":       list(df.columns),
    "class_counts": {
        "sf":     df["label_sf"].value_counts().sort_index().to_dict(),
        "mod":    df["label_mod"].value_counts().to_dict(),
        "beacon": df["label_beacon"].value_counts().sort_index().to_dict(),
        "pkt":    df["label_pkt"].value_counts().sort_index().to_dict(),
    },
    "regime_counts": df["regime"].value_counts().to_dict(),
    "split_counts":  df["split"].value_counts().to_dict(),
    "data_row_label_mismatches": n_mismatch,
    "checks_passed": len(CHECKS),
}
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
log.info(f"Wrote {MANIFEST_PATH}")
log.info("=== load_and_validate.py done ===")
