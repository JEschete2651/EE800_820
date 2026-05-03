"""LH4-B - Preprocessing pipeline and feature selection.

Reads merged_dataset.csv, drops join-mid-stream artifact rows, builds
per-task feature matrices avoiding label leakage, fits StandardScaler
on train, and saves .npy artifacts plus a preprocessor.pkl per task.

Run:
    python preprocess.py
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
MERGED_CSV    = SCRIPT_DIR.parent / "Tools" / "CampaignCollect" / "merged_dataset.csv"
MANIFEST_PATH = SCRIPT_DIR / "preprocess_manifest.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"preprocess_{run_stamp}.log"
log_latest  = LOG_DIR / "preprocess_latest.log"

log = logging.getLogger("preprocess")
log.setLevel(logging.DEBUG)
log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt)
    log.addHandler(h)

log.info("=== preprocess.py starting ===")
log.info(f"Run stamp: {run_stamp}")
log.info(f"Source CSV: {MERGED_CSV}")
log.info(f"Archive log: {log_archive}")

if not MERGED_CSV.exists():
    log.error(f"merged_dataset.csv not found at {MERGED_CSV}")
    log.error("Run Code/Tools/CampaignCollect/merge_dataset.py first.")
    sys.exit(1)

df = pd.read_csv(MERGED_CSV)
n0 = len(df)
df = df[df["inter_arrival_ms"] > 0].reset_index(drop=True)
log.info(f"Dropped {n0 - len(df)} join-artifact rows "
         f"({(n0 - len(df))/n0:.1%}); {len(df):,} rows remain")


FEATURE_COLS_BASE = [
    "rssi_dbm", "snr_db", "freq_error_hz",
    "inter_arrival_ms", "payload_len",
    "spread_factor", "mod_kind", "beacon_id", "pkt_type",
    "distance_m",
]

FORBIDDEN = {
    "sf":     ["spread_factor", "freq_error_hz"],
    "mod":    ["mod_kind", "spread_factor"],
    "beacon": ["beacon_id"],
    "pkt":    ["pkt_type"],
}

LABEL_COL = {
    "sf":     "label_sf",
    "mod":    "label_mod",
    "beacon": "label_beacon",
    "pkt":    "label_pkt",
}


class Preprocessor:
    def __init__(self, task):
        assert task in FORBIDDEN, f"Unknown task: {task}"
        self.task = task
        self.feature_cols = [c for c in FEATURE_COLS_BASE
                             if c not in FORBIDDEN[task]]
        self.scaler = StandardScaler()
        self.encoder = LabelEncoder()

    def fit_transform(self, df):
        tr = df[df["split"] == "train"]
        if tr.empty:
            raise RuntimeError(
                f"Task {self.task}: no training rows after filtering")
        # Drop zero-variance columns: StandardScaler can't scale them
        # (std=0 produces NaN or 0/0), and they carry no information
        # for any model. In the current dataset payload_len, distance_m,
        # and (in non-mod tasks) mod_kind are constant.
        X_full = tr[self.feature_cols].to_numpy(dtype=np.float32)
        std = X_full.std(axis=0)
        keep = std > 0
        dropped = [c for c, k in zip(self.feature_cols, keep) if not k]
        if dropped:
            log.warning(f"Task {self.task}: dropping zero-variance "
                        f"features: {dropped}")
        self.feature_cols = [c for c, k in zip(self.feature_cols, keep) if k]
        X_tr = X_full[:, keep]
        y_tr = self.encoder.fit_transform(tr[LABEL_COL[self.task]])
        X_tr = self.scaler.fit_transform(X_tr)
        return X_tr, y_tr

    def transform(self, df, split):
        sp = df[df["split"] == split]
        if sp.empty:
            return (np.empty((0, len(self.feature_cols)), dtype=np.float32),
                    np.empty((0,), dtype=np.int64))
        X = sp[self.feature_cols].to_numpy(dtype=np.float32)
        known = np.isin(sp[LABEL_COL[self.task]].to_numpy(),
                        self.encoder.classes_)
        if (~known).any():
            log.warning(f"Task {self.task} split={split}: dropping "
                        f"{(~known).sum()} rows with unseen labels "
                        f"{set(sp.loc[~known, LABEL_COL[self.task]])}")
        sp = sp[known]; X = X[known]
        y = self.encoder.transform(sp[LABEL_COL[self.task]])
        X = self.scaler.transform(X)
        return X, y

    def save(self, out_dir):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        joblib.dump({"scaler": self.scaler,
                     "encoder": self.encoder,
                     "feature_cols": self.feature_cols,
                     "task": self.task}, out / "preprocessor.pkl")


manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_stamp":    run_stamp,
    "source_file":  str(MERGED_CSV),
    "log_archive":  str(log_archive),
    "rows_after_artifact_drop": int(len(df)),
    "tasks": {},
}

for task in ["sf", "mod", "beacon", "pkt"]:
    log.info(f"--- Task: {task} ---")
    pre = Preprocessor(task)
    X_tr, y_tr = pre.fit_transform(df)
    X_va, y_va = pre.transform(df, "val")
    X_te, y_te = pre.transform(df, "test")

    log.info(f"Features ({len(pre.feature_cols)}): {pre.feature_cols}")
    log.info(f"Classes ({len(pre.encoder.classes_)}): "
             f"{list(pre.encoder.classes_)}")
    log.info(f"Shapes: X_tr={X_tr.shape}, X_va={X_va.shape}, X_te={X_te.shape}")

    out = ARTIFACTS_DIR / task
    pre.save(out)
    np.save(out / "X_train.npy", X_tr); np.save(out / "y_train.npy", y_tr)
    np.save(out / "X_val.npy",   X_va); np.save(out / "y_val.npy",   y_va)
    np.save(out / "X_test.npy",  X_te); np.save(out / "y_test.npy",  y_te)
    log.info(f"Saved artifacts to {out}")

    manifest["tasks"][task] = {
        "feature_cols":  pre.feature_cols,
        "forbidden":     FORBIDDEN[task],
        "label_col":     LABEL_COL[task],
        "classes":       [str(c) for c in pre.encoder.classes_],
        "n_train":       int(X_tr.shape[0]),
        "n_val":         int(X_va.shape[0]),
        "n_test":        int(X_te.shape[0]),
    }


log.info("=== Scaler verification ===")
for task in ["sf", "mod", "beacon", "pkt"]:
    X_tr = np.load(ARTIFACTS_DIR / task / "X_train.npy")
    mu, sd = X_tr.mean(axis=0), X_tr.std(axis=0)
    log.info(f"{task}: max|mu|={np.abs(mu).max():.3e}, "
             f"std range=[{sd.min():.3f}, {sd.max():.3f}]")
    assert np.abs(mu).max() < 1e-4, f"{task}: scaler mean drifted"
    assert np.all(np.abs(sd - 1) < 1e-4), f"{task}: scaler std drifted"


log.info("=== Leakage sanity check (forbidden-only logistic regression) ===")
for task, bad in FORBIDDEN.items():
    tr = df[df["split"] == "train"]
    te = df[df["split"] == "test"]
    n_classes_train = tr[LABEL_COL[task]].nunique()
    if n_classes_train < 2:
        log.warning(f"{task}: only {n_classes_train} class in train --- "
                    f"skipping leakage check (current dataset has only "
                    f"LoRa modulation; will become meaningful once C3 "
                    f"or other modulations are collected)")
        continue
    enc = LabelEncoder()
    y_tr = enc.fit_transform(tr[LABEL_COL[task]])
    known = np.isin(te[LABEL_COL[task]].to_numpy(), enc.classes_)
    te_kept = te[known]
    if te_kept.empty:
        log.warning(f"{task}: no test rows match training classes --- "
                    f"skipping leakage check")
        continue
    y_te = enc.transform(te_kept[LABEL_COL[task]])
    X_tr = tr[bad].to_numpy(dtype=float)
    X_te = te_kept[bad].to_numpy(dtype=float)
    sc = StandardScaler().fit(X_tr)
    clf = LogisticRegression(max_iter=1000).fit(sc.transform(X_tr), y_tr)
    acc = clf.score(sc.transform(X_te), y_te)
    log.info(f"{task} (forbidden-only features {bad}): test acc = {acc:.3f}")
    manifest["tasks"][task]["leakage_forbidden_only_acc"] = float(acc)


with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
log.info(f"Wrote {MANIFEST_PATH}")
log.info("=== preprocess.py done ===")
