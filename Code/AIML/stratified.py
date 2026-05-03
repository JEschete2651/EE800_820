"""LH4-G - Stratified accuracy by SNR, distance, active-station count.

For every task with >=2 classes, computes per-bucket test accuracy with
Wilson 95% CIs for RF/SVM/MLP/CNN. Produces a three-panel figure per
task (SNR quintiles | distance | active-station count) and a worst-
bucket robustness summary. Distance and station panels are auto-skipped
when the test split lacks variation in those columns.

Run:
    python stratified.py
"""
import json
import logging
import sys
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from scipy.stats import norm

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
FIGS_DIR      = SCRIPT_DIR / "figs"
MANIFEST_PATH = SCRIPT_DIR / "stratified_manifest.json"
MERGED_CSV    = SCRIPT_DIR.parent / "Tools" / "CampaignCollect" / "merged_dataset.csv"

LOG_DIR.mkdir(parents=True, exist_ok=True)
FIGS_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"stratified_{run_stamp}.log"
log_latest  = LOG_DIR / "stratified_latest.log"

log = logging.getLogger("stratified")
log.setLevel(logging.DEBUG)
log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt)
    log.addHandler(h)

log.info("=== stratified.py starting ===")
log.info(f"Run stamp: {run_stamp}")
log.info(f"Archive log: {log_archive}")

LABEL_COL = {"sf": "label_sf", "mod": "label_mod",
             "beacon": "label_beacon", "pkt": "label_pkt"}
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
log.info(f"PyTorch device: {DEVICE}")


# Inlined model classes so we don't re-execute mlp_train/cnn_train at import.
class MLP(nn.Module):
    def __init__(self, n_features, n_classes, hidden=(64, 32), p=0.3):
        super().__init__()
        layers = []; prev = n_features
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(p)]
            prev = h
        layers.append(nn.Linear(prev, n_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class CNN1D(nn.Module):
    def __init__(self, n_features, n_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(n_features, 16, kernel_size=3, padding=1), nn.ReLU(),
            nn.Conv1d(16,         32, kernel_size=3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(32, 32), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(32, n_classes),
        )

    def forward(self, x):
        return self.net(x.transpose(1, 2))


def wilson_ci(n_correct, n_total, alpha=0.05):
    if n_total == 0:
        return 0.0, 1.0
    p = n_correct / n_total
    z = norm.ppf(1 - alpha / 2)
    denom = 1 + z * z / n_total
    center = (p + z * z / (2 * n_total)) / denom
    half = z * sqrt(p * (1 - p) / n_total
                    + z * z / (4 * n_total * n_total)) / denom
    return max(0.0, center - half), min(1.0, center + half)


df_full = pd.read_csv(MERGED_CSV)
df_full = df_full[df_full["inter_arrival_ms"] > 0].reset_index(drop=True)
test_df = df_full[df_full["split"] == "test"].copy()
log.info(f"Loaded {len(df_full)} rows; {len(test_df)} test rows")


def predict_row_model(task, model_kind):
    pre = joblib.load(ARTIFACTS_DIR / task / "preprocessor.pkl")
    feats = pre["feature_cols"]
    raw = test_df[LABEL_COL[task]].to_numpy()
    known = np.isin(raw, pre["encoder"].classes_)
    sub = test_df[known]
    if len(sub) == 0:
        return None, None, None
    X = pre["scaler"].transform(sub[feats].to_numpy(dtype=np.float32))
    y_true = pre["encoder"].transform(sub[LABEL_COL[task]])
    if model_kind in ("rf", "svm"):
        bundle = joblib.load(ARTIFACTS_DIR / task / f"{model_kind}.pkl")
        y_pred = bundle["model"].predict(X)
    elif model_kind == "mlp":
        pkl = torch.load(ARTIFACTS_DIR / task / "mlp.pt", weights_only=False)
        m = MLP(pkl["n_features"], pkl["n_classes"]).to(DEVICE)
        m.load_state_dict(pkl["state_dict"]); m.eval()
        with torch.no_grad():
            y_pred = m(torch.from_numpy(X).float().to(DEVICE)
                       ).argmax(1).cpu().numpy()
    else:
        raise ValueError(model_kind)
    return y_pred, y_true, sub.index.to_numpy()


def predict_cnn(task):
    pkl = torch.load(ARTIFACTS_DIR / task / "cnn.pt", weights_only=False)
    Xs = np.load(ARTIFACTS_DIR / task / "Xs_test.npy")
    ys = np.load(ARTIFACTS_DIR / task / "ys_test.npy")
    src_path = ARTIFACTS_DIR / task / "src_test.npy"
    if not src_path.exists():
        log.warning(f"  {task}: src_test.npy missing --- "
                    f"re-run cnn_train.py to regenerate alignment indices.")
        return None, None, None
    src = np.load(src_path)
    if len(Xs) == 0:
        return None, None, None
    m = CNN1D(pkl["n_features"], pkl["n_classes"]).to(DEVICE)
    m.load_state_dict(pkl["state_dict"]); m.eval()
    with torch.no_grad():
        y_pred = m(torch.from_numpy(Xs).float().to(DEVICE)
                   ).argmax(1).cpu().numpy()
    return y_pred, ys, src


def predict(task, model_kind):
    if model_kind == "cnn":
        return predict_cnn(task)
    return predict_row_model(task, model_kind)


def stratified_acc(task, stratifier_col, edges_or_values, ax, title,
                   continuous=True):
    """Plot per-model accuracy across buckets and return a summary dict."""
    handles = []
    bucket_summary = {}
    for model_kind in ["rf", "svm", "mlp", "cnn"]:
        try:
            y_pred, y_true, src = predict(task, model_kind)
        except Exception as e:
            log.warning(f"  {task} {model_kind}: predict failed: {e}")
            continue
        if y_pred is None:
            continue
        strat = df_full.loc[src, stratifier_col].to_numpy()
        accs = []; ns = []; los = []; his = []; centers = []
        if continuous:
            edges = np.asarray(edges_or_values, dtype=float)
            interior = edges[1:-1]
            idx = np.digitize(strat, interior)
            n_b = len(edges) - 1
            for b in range(n_b):
                m = (idx == b); n = int(m.sum())
                center = float(0.5 * (edges[b] + edges[b + 1]))
                centers.append(center)
                if n == 0:
                    accs.append(np.nan); ns.append(0); los.append(np.nan); his.append(np.nan)
                    continue
                nc = int((y_pred[m] == y_true[m]).sum())
                accs.append(nc / n); ns.append(n)
                lo, hi = wilson_ci(nc, n); los.append(lo); his.append(hi)
        else:
            for v in edges_or_values:
                m = (strat == v); n = int(m.sum())
                centers.append(float(v))
                if n == 0:
                    accs.append(np.nan); ns.append(0); los.append(np.nan); his.append(np.nan)
                    continue
                nc = int((y_pred[m] == y_true[m]).sum())
                accs.append(nc / n); ns.append(n)
                lo, hi = wilson_ci(nc, n); los.append(lo); his.append(hi)
        for c, n in zip(centers, ns):
            if 0 < n < 30:
                log.warning(f"  {task} {model_kind} bucket center={c:.2f}: "
                            f"n={n} (<30, noisy)")
        h, = ax.plot(centers, accs, "-o", label=model_kind.upper())
        handles.append(h)
        bucket_summary[model_kind] = {
            "centers": centers, "accs": accs, "ns": ns,
            "ci_lo": los, "ci_hi": his,
        }
    ax.set_title(title); ax.grid(True)
    if handles:
        ax.legend(handles=handles, fontsize=7)
    return bucket_summary


def plot_task(task):
    if task == "mod":
        log.info(f"  {task}: only LoRa collected --- skipping")
        return None

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # Panel 1: SNR quintiles
    snrs = test_df["snr_db"].to_numpy()
    edges = np.quantile(snrs, np.linspace(0, 1, 6))
    snr_summary = stratified_acc(task, "snr_db", edges, axes[0],
                                 f"{task}: acc vs SNR (quintiles)",
                                 continuous=True)
    axes[0].set_xlabel("SNR (dB) bucket center")
    axes[0].set_ylabel("Test accuracy")

    # Panel 2: distance
    distances = sorted(test_df["distance_m"].unique())
    if len(distances) < 2:
        axes[1].set_title(f"{task}: distance plot SKIPPED")
        axes[1].text(0.5, 0.5, "C4 not collected\n(distance_m constant)",
                     ha="center", va="center", transform=axes[1].transAxes)
        axes[1].set_xticks([]); axes[1].set_yticks([])
        dist_summary = None
        log.info(f"  {task}: distance panel skipped (no variation)")
    else:
        dist_summary = stratified_acc(task, "distance_m", distances,
                                      axes[1], f"{task}: acc vs distance",
                                      continuous=False)
        axes[1].set_xlabel("Distance (m)")
        axes[1].set_ylabel("Test accuracy")

    # Panel 3: active stations (C5a -> 1, C5b -> 2)
    runs = test_df["run_id"].to_numpy().astype(str)
    stations = np.where(np.char.startswith(runs, "C5b"), 2,
                np.where(np.char.startswith(runs, "C5a"), 1, 0))
    df_full.loc[test_df.index, "_stations"] = stations
    discrete = sorted(set(stations.tolist()) - {0})
    if len(discrete) < 2:
        axes[2].set_title(f"{task}: stations plot SKIPPED")
        axes[2].text(0.5, 0.5, "Need both C5a and C5b in test",
                     ha="center", va="center", transform=axes[2].transAxes)
        axes[2].set_xticks([]); axes[2].set_yticks([])
        sta_summary = None
        log.info(f"  {task}: stations panel skipped (only one C5 sub-config)")
    else:
        sta_summary = stratified_acc(task, "_stations", discrete,
                                     axes[2], f"{task}: acc vs active stations",
                                     continuous=False)
        axes[2].set_xlabel("Active station count")
        axes[2].set_ylabel("Test accuracy")
        axes[2].set_xticks(discrete)

    fig.tight_layout()
    out = FIGS_DIR / f"stratified_{task}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info(f"  Saved {out}")
    return {"snr": snr_summary, "distance": dist_summary, "stations": sta_summary}


task_results = {}
for task in ["sf", "mod", "beacon", "pkt"]:
    log.info(f"--- Task: {task} ---")
    task_results[task] = plot_task(task)


log.info("=== Worst-bucket robustness (SNR quintiles) ===")
log.info(f"{'Task':<8} {'Model':<5} {'min':>8} {'mean':>8} {'max':>8}")
robustness = {}
for task, res in task_results.items():
    if not res or not res.get("snr"):
        continue
    robustness[task] = {}
    for model_kind, info in res["snr"].items():
        accs = np.asarray(info["accs"], dtype=float)
        if np.all(np.isnan(accs)):
            continue
        mn   = float(np.nanmin(accs))
        mx   = float(np.nanmax(accs))
        mean = float(np.nanmean(accs))
        log.info(f"{task:<8} {model_kind:<5} {mn:>8.3f} {mean:>8.3f} {mx:>8.3f}")
        robustness[task][model_kind] = {"min": mn, "mean": mean, "max": mx}


manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_stamp":    run_stamp,
    "log_archive":  str(log_archive),
    "results":      task_results,
    "robustness":   robustness,
}
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, default=str)
log.info(f"Wrote {MANIFEST_PATH}")
log.info("=== stratified.py done ===")
