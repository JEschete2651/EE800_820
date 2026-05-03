"""LH4-F - 1-D CNN over feature sequences and the operating-condition shift.

For each task with >=2 classes, builds (T=8, F) sliding-window sequences
grouped by (run_id, beacon_id), trains a small Conv1d -> Conv1d ->
GlobalAvgPool -> MLP head with early stopping, runs the
clean->clean / clean->contended op-shift experiment, and fine-tunes
the final layer on a small slice of contended training data.

Run:
    python cnn_train.py
"""
import json
import logging
import sys
import time
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
from torch.utils.data import DataLoader, TensorDataset

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
FIGS_DIR      = SCRIPT_DIR / "figs"
MANIFEST_PATH = SCRIPT_DIR / "cnn_manifest.json"
MERGED_CSV    = SCRIPT_DIR.parent / "Tools" / "CampaignCollect" / "merged_dataset.csv"

LOG_DIR.mkdir(parents=True, exist_ok=True)
FIGS_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"cnn_train_{run_stamp}.log"
log_latest  = LOG_DIR / "cnn_train_latest.log"

log = logging.getLogger("cnn_train")
log.setLevel(logging.DEBUG)
log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt)
    log.addHandler(h)

log.info("=== cnn_train.py starting ===")
log.info(f"Run stamp: {run_stamp}")
log.info(f"Archive log: {log_archive}")

WINDOW = 8
LABEL_COL = {"sf": "label_sf", "mod": "label_mod",
             "beacon": "label_beacon", "pkt": "label_pkt"}
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
log.info(f"PyTorch device: {DEVICE}")


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


def build_sequences(task):
    df = pd.read_csv(MERGED_CSV)
    df = df[df["inter_arrival_ms"] > 0].reset_index(drop=True)

    pre = joblib.load(ARTIFACTS_DIR / task / "preprocessor.pkl")
    feats = pre["feature_cols"]
    X_all = pre["scaler"].transform(df[feats].to_numpy(dtype=np.float32))

    classes = pre["encoder"].classes_
    raw_labels = df[LABEL_COL[task]].to_numpy()
    known = np.isin(raw_labels, classes)
    if (~known).any():
        log.warning(f"  {task}: {int((~known).sum())} rows have labels "
                    f"not seen at fit time; dropping")
    df = df[known].reset_index(drop=True)
    X_all = X_all[known]
    y_all = pre["encoder"].transform(df[LABEL_COL[task]])

    seqs, labels, splits, regimes, src_idx = [], [], [], [], []
    for (_, _), grp in df.groupby(["run_id", "beacon_id"], sort=False):
        idxs = grp.index.to_numpy()
        for i, r in enumerate(idxs):
            lo = max(0, i - WINDOW + 1)
            win_idxs = idxs[lo:i + 1]
            window = X_all[win_idxs]
            if len(window) < WINDOW:
                pad = np.zeros((WINDOW - len(window), window.shape[1]),
                               dtype=np.float32)
                window = np.concatenate([pad, window], axis=0)
            seqs.append(window)
            labels.append(y_all[r])
            splits.append(df.at[r, "split"])
            regimes.append(df.at[r, "regime"])
            src_idx.append(int(r))

    seqs    = np.stack(seqs).astype(np.float32)
    labels  = np.asarray(labels, dtype=np.int64)
    splits  = np.asarray(splits)
    regimes = np.asarray(regimes)
    src_idx = np.asarray(src_idx, dtype=np.int64)
    for name in ["train", "val", "test"]:
        mask = splits == name
        np.save(ARTIFACTS_DIR / task / f"Xs_{name}.npy",   seqs[mask])
        np.save(ARTIFACTS_DIR / task / f"ys_{name}.npy",   labels[mask])
        np.save(ARTIFACTS_DIR / task / f"regs_{name}.npy", regimes[mask])
        # Source-row index of each sequence's *target* row in the
        # post-artifact-drop merged dataset. LH4-G uses this to align
        # CNN predictions with row-level stratifiers (SNR, distance,
        # active-station count).
        np.save(ARTIFACTS_DIR / task / f"src_{name}.npy", src_idx[mask])
        log.info(f"  {task} {name}: {mask.sum()} sequences of shape "
                 f"{seqs.shape[1:]}; "
                 f"clean={(regimes[mask]=='clean').sum()}, "
                 f"contended={(regimes[mask]=='contended').sum()}")
    return seqs.shape[2]


def train_cnn(Xs_tr, ys_tr, Xs_va, ys_va, n_classes, seed=42,
              epochs=200, patience=15, lr=1e-3, batch_size=32):
    torch.manual_seed(seed); np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model = CNN1D(Xs_tr.shape[2], n_classes).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    ds = TensorDataset(torch.from_numpy(Xs_tr).float(),
                       torch.from_numpy(ys_tr).long())
    ld = DataLoader(ds, batch_size=batch_size, shuffle=True)
    if len(Xs_va):
        X_va_t = torch.from_numpy(Xs_va).float().to(DEVICE)
        y_va_t = torch.from_numpy(ys_va).long().to(DEVICE)
    else:
        X_va_t = y_va_t = None

    best_val, best_state, bad = float("inf"), None, 0
    history = {"train_loss": [], "val_loss": []}
    for ep in range(epochs):
        model.train()
        total = 0.0
        for xb, yb in ld:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward(); opt.step()
            total += loss.item() * len(xb)
        history["train_loss"].append(total / max(len(ds), 1))
        if X_va_t is not None:
            model.eval()
            with torch.no_grad():
                v_loss = loss_fn(model(X_va_t), y_va_t).item()
            history["val_loss"].append(v_loss)
            if v_loss < best_val - 1e-4:
                best_val, bad = v_loss, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
        else:
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history


@torch.no_grad()
def accuracy(model, Xs, ys):
    if len(Xs) == 0:
        return float("nan"), 0, 0
    model.eval()
    xb = torch.from_numpy(Xs).float().to(DEVICE)
    pred = model(xb).argmax(1).cpu().numpy()
    n_correct = int((pred == ys).sum())
    return n_correct / len(ys), n_correct, len(ys)


def load_regime_split(task, regime, split):
    Xs = np.load(ARTIFACTS_DIR / task / f"Xs_{split}.npy")
    ys = np.load(ARTIFACTS_DIR / task / f"ys_{split}.npy")
    rs = np.load(ARTIFACTS_DIR / task / f"regs_{split}.npy")
    mask = (rs == regime)
    return Xs[mask], ys[mask]


# Step 1+2: build sequences and run canonical training per task
results = {}
for task in ["sf", "mod", "beacon", "pkt"]:
    log.info(f"--- Task: {task} ---")
    pre = joblib.load(ARTIFACTS_DIR / task / "preprocessor.pkl")
    n_classes = len(pre["encoder"].classes_)
    if n_classes < 2:
        log.warning(f"  {task}: only {n_classes} class --- "
                    f"skipping CNN (cross-entropy degenerate for one class)")
        results[task] = {"skipped": True, "reason": "single class in train"}
        continue

    log.info(f"  Building sequences (window={WINDOW})...")
    n_features = build_sequences(task)
    Xs_tr = np.load(ARTIFACTS_DIR / task / "Xs_train.npy")
    ys_tr = np.load(ARTIFACTS_DIR / task / "ys_train.npy")
    Xs_va = np.load(ARTIFACTS_DIR / task / "Xs_val.npy")
    ys_va = np.load(ARTIFACTS_DIR / task / "ys_val.npy")
    Xs_te = np.load(ARTIFACTS_DIR / task / "Xs_test.npy")
    ys_te = np.load(ARTIFACTS_DIR / task / "ys_test.npy")

    t0 = time.time()
    model, history = train_cnn(Xs_tr, ys_tr, Xs_va, ys_va, n_classes)
    elapsed = time.time() - t0
    acc_te, nc, nt = accuracy(model, Xs_te, ys_te)
    lo, hi = wilson_ci(nc, nt)
    log.info(f"  CNN test acc = {acc_te:.3f}  [95% CI {lo:.3f}, {hi:.3f}]  "
             f"({nc}/{nt})  trained in {elapsed:.1f}s, "
             f"epochs={len(history['train_loss'])}")
    torch.save({"state_dict": model.state_dict(),
                "n_features": n_features, "n_classes": n_classes,
                "seed": 42, "test_acc": acc_te, "ci": [lo, hi],
                "elapsed_s": elapsed, "history": history},
               ARTIFACTS_DIR / task / "cnn.pt")
    log.info(f"  Saved {ARTIFACTS_DIR / task / 'cnn.pt'}")

    results[task] = {
        "test_acc": acc_te, "ci_lo": lo, "ci_hi": hi,
        "n_correct": nc, "n_total": nt, "elapsed_s": elapsed,
        "n_features": n_features, "n_classes": n_classes,
        "feature_cols": pre["feature_cols"],
    }

# Step 3: clean->clean / clean->contended op-shift
for task, res in results.items():
    if res.get("skipped"):
        continue
    log.info(f"--- Op-shift: {task} ---")
    X_tr, y_tr = load_regime_split(task, "clean", "train")
    X_va, y_va = load_regime_split(task, "clean", "val")
    n_classes  = res["n_classes"]
    if len(X_tr) == 0:
        log.warning(f"  {task}: no clean-regime training rows --- "
                    f"skipping op-shift")
        res["op_shift"] = {"skipped": True, "reason": "no clean train"}
        continue

    log.info(f"  Train clean only: {len(X_tr)} train, {len(X_va)} val")
    t0 = time.time()
    clean_model, _ = train_cnn(X_tr, y_tr, X_va, y_va, n_classes)
    log.info(f"  Trained in {time.time() - t0:.1f}s")

    X_cc, y_cc = load_regime_split(task, "clean",     "test")
    X_cn, y_cn = load_regime_split(task, "contended", "test")
    acc_cc, nc_cc, nt_cc = accuracy(clean_model, X_cc, y_cc)
    acc_cn, nc_cn, nt_cn = accuracy(clean_model, X_cn, y_cn)
    delta = acc_cc - acc_cn if not np.isnan(acc_cn) else float("nan")
    log.info(f"  clean->clean     = {acc_cc:.3f}  ({nc_cc}/{nt_cc})")
    log.info(f"  clean->contended = {acc_cn:.3f}  ({nc_cn}/{nt_cn})")
    log.info(f"  Delta            = {delta:+.3f}")

    res["op_shift"] = {
        "acc_clean_clean":     acc_cc,
        "acc_clean_contended": acc_cn,
        "delta":               delta,
        "n_clean_test":        nt_cc, "n_contended_test": nt_cn,
        "clean_train_size":    int(len(X_tr)),
    }
    res["_clean_state"] = {k: v.cpu().clone()
                           for k, v in clean_model.state_dict().items()}


# Step 4: fine-tune the final layer on a small contended train slice
def finetune_last_layer(task, n_features, n_classes, clean_state,
                        fraction=0.20, epochs=40, batch=32, lr=1e-3,
                        seed=42):
    torch.manual_seed(seed); np.random.seed(seed)
    model = CNN1D(n_features, n_classes).to(DEVICE)
    model.load_state_dict(clean_state)
    for p in model.parameters():           p.requires_grad = False
    for p in model.net[-1].parameters():   p.requires_grad = True

    X_ft, y_ft = load_regime_split(task, "contended", "train")
    if len(X_ft) == 0:
        log.warning(f"  {task}: no contended train --- skipping fine-tune")
        return None
    rng = np.random.default_rng(seed=seed)
    n_keep = max(1, int(fraction * len(X_ft)))
    keep = rng.choice(len(X_ft), size=n_keep, replace=False)
    X_ft, y_ft = X_ft[keep], y_ft[keep]
    log.info(f"  Fine-tuning on {n_keep}/{len(load_regime_split(task, 'contended', 'train')[0])} "
             f"contended train rows (fraction={fraction})")

    ds = TensorDataset(torch.from_numpy(X_ft).float(),
                       torch.from_numpy(y_ft).long())
    dl = DataLoader(ds, batch_size=batch, shuffle=True)
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad],
                           lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for xb, yb in dl:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            opt.zero_grad()
            loss_fn(model(xb), yb).backward()
            opt.step()

    X_ev, y_ev = load_regime_split(task, "contended", "test")
    acc_ft, nc, nt = accuracy(model, X_ev, y_ev)
    return {"acc": acc_ft, "n_correct": nc, "n_total": nt,
            "n_finetune_rows": int(n_keep), "fraction": fraction}


for task, res in results.items():
    if res.get("skipped") or res.get("op_shift", {}).get("skipped"):
        continue
    log.info(f"--- Fine-tune: {task} ---")
    state = res.pop("_clean_state")
    ft = finetune_last_layer(task, res["n_features"], res["n_classes"], state)
    if ft is None:
        continue
    res["finetune"] = ft
    op = res["op_shift"]
    recovered = ft["acc"] - op["acc_clean_contended"]
    log.info(f"  contended-finetune test acc = {ft['acc']:.3f}  "
             f"(was {op['acc_clean_contended']:.3f}, "
             f"recovered {recovered:+.3f})")
    res["finetune"]["recovered"] = recovered


# Step 5: summary table + manifest
log.info("=== Op-shift summary ===")
log.info(f"{'Task':<8} {'CNN test':>10} {'cln->cln':>10} "
         f"{'cln->cnt':>10} {'Delta':>10} {'finetune':>10} {'recover':>10}")
for task in ["sf", "mod", "beacon", "pkt"]:
    res = results[task]
    if res.get("skipped"):
        log.info(f"{task:<8} (skipped)  reason: {res['reason']}")
        continue
    op = res.get("op_shift", {})
    ft = res.get("finetune", {})
    fmt_or_na = lambda v: f"{v:>10.3f}" if isinstance(v, float) and not np.isnan(v) \
        else f"{'n/a':>10}"
    fmt_signed = lambda v: f"{v:>+10.3f}" if isinstance(v, float) and not np.isnan(v) \
        else f"{'n/a':>10}"
    log.info(f"{task:<8} "
             f"{fmt_or_na(res['test_acc'])} "
             f"{fmt_or_na(op.get('acc_clean_clean', float('nan')))} "
             f"{fmt_or_na(op.get('acc_clean_contended', float('nan')))} "
             f"{fmt_signed(op.get('delta', float('nan')))} "
             f"{fmt_or_na(ft.get('acc', float('nan')))} "
             f"{fmt_signed(ft.get('recovered', float('nan')))}")


manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_stamp":    run_stamp,
    "log_archive":  str(log_archive),
    "device":       str(DEVICE),
    "window":       WINDOW,
    "results":      results,
}
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, default=str)
log.info(f"Wrote {MANIFEST_PATH}")
log.info("=== cnn_train.py done ===")
