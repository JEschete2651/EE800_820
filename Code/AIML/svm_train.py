"""LH4-D - SVM grid search, confusion matrix, and permutation importance.

For each task with >=2 classes, fits a grid-searched SVC over linear and
RBF kernels, reports test accuracy with a 95% Wilson CI, plots the
confusion matrix and permutation importance, and computes Spearman rank
correlation between SVM permutation importance and RF Gini importance.

Run:
    python svm_train.py
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
from scipy.stats import norm, spearmanr
from sklearn.inspection import permutation_importance
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score,
                             classification_report, confusion_matrix)
from sklearn.model_selection import GridSearchCV
from sklearn.svm import SVC

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
FIGS_DIR      = SCRIPT_DIR / "figs"
MANIFEST_PATH = SCRIPT_DIR / "svm_manifest.json"
RF_MANIFEST   = SCRIPT_DIR / "baselines_manifest.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
FIGS_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"svm_train_{run_stamp}.log"
log_latest  = LOG_DIR / "svm_train_latest.log"

log = logging.getLogger("svm_train")
log.setLevel(logging.DEBUG)
log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt)
    log.addHandler(h)

log.info("=== svm_train.py starting ===")
log.info(f"Run stamp: {run_stamp}")
log.info(f"Archive log: {log_archive}")


def load_task(task):
    d = ARTIFACTS_DIR / task
    X_tr = np.load(d / "X_train.npy"); y_tr = np.load(d / "y_train.npy")
    X_va = np.load(d / "X_val.npy");   y_va = np.load(d / "y_val.npy")
    X_te = np.load(d / "X_test.npy");  y_te = np.load(d / "y_test.npy")
    pre  = joblib.load(d / "preprocessor.pkl")
    return X_tr, y_tr, X_va, y_va, X_te, y_te, pre


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


SVM_GRID = [
    {"kernel": ["linear"], "C": [0.1, 1, 10]},
    {"kernel": ["rbf"],    "C": [0.1, 1, 10, 100],
                           "gamma": ["scale", 0.01, 0.1, 1.0]},
]
n_combos = sum(
    (len(g.get("C", [None])) * len(g.get("gamma", [None])) * len(g["kernel"]))
    for g in SVM_GRID
)
log.info(f"SVM grid: {n_combos} hyperparameter combos x 5 folds = "
         f"{n_combos * 5} fits per task")


results = {}
for task in ["sf", "mod", "beacon", "pkt"]:
    log.info(f"--- Task: {task} ---")
    X_tr, y_tr, X_va, y_va, X_te, y_te, pre = load_task(task)
    n_classes = len(np.unique(y_tr))
    log.info(f"  Train shape={X_tr.shape}, classes={n_classes}, "
             f"features={pre['feature_cols']}")
    if n_classes < 2:
        log.warning(f"  {task}: only {n_classes} class --- skipping (SVC needs >=2)")
        results[task] = {"skipped": True, "reason": "single class in train"}
        continue

    X_cv = np.concatenate([X_tr, X_va]); y_cv = np.concatenate([y_tr, y_va])
    t0 = time.time()
    log.info(f"  Running SVM grid search ({n_combos * 5} fits)...")
    gs = GridSearchCV(SVC(random_state=42),
                      SVM_GRID, cv=5, scoring="accuracy",
                      n_jobs=-1, verbose=0)
    gs.fit(X_cv, y_cv)
    elapsed = time.time() - t0
    log.info(f"  Grid search complete in {elapsed:.1f}s; "
             f"best params: {gs.best_params_}")

    best = gs.best_estimator_
    y_pred = best.predict(X_te)
    n_correct = int((y_pred == y_te).sum())
    acc_te = n_correct / len(y_te)
    lo, hi = wilson_ci(n_correct, len(y_te))
    log.info(f"  CV acc = {gs.best_score_:.3f}  test acc = {acc_te:.3f}  "
             f"[95% CI {lo:.3f}, {hi:.3f}]  ({n_correct}/{len(y_te)})")

    joblib.dump({"model": best, "cv_acc": float(gs.best_score_),
                 "test_acc": acc_te, "ci": [lo, hi],
                 "params": gs.best_params_, "elapsed_s": elapsed},
                ARTIFACTS_DIR / task / "svm.pkl")
    log.info(f"  Saved {ARTIFACTS_DIR / task / 'svm.pkl'}")

    results[task] = {
        "kernel":   gs.best_params_.get("kernel"),
        "C":        gs.best_params_.get("C"),
        "gamma":    gs.best_params_.get("gamma"),
        "cv_acc":   float(gs.best_score_),
        "test_acc": acc_te, "ci_lo": lo, "ci_hi": hi,
        "n_correct": n_correct, "n_total": len(y_te),
        "elapsed_s": elapsed,
        "feature_cols": pre["feature_cols"],
    }


# Step 2: classification report and confusion matrix
for task, res in results.items():
    if res.get("skipped"):
        continue
    pkl = joblib.load(ARTIFACTS_DIR / task / "svm.pkl")
    svm = pkl["model"]
    _, _, _, _, X_te, y_te, pre = load_task(task)
    y_pred = svm.predict(X_te)
    log.info(f"--- {task} SVM classification report ---")
    all_label_ids = list(range(len(pre["encoder"].classes_)))
    report = classification_report(
        y_te, y_pred,
        labels=all_label_ids,
        target_names=[str(c) for c in pre["encoder"].classes_],
        zero_division=0)
    for line in report.splitlines():
        if line.strip():
            log.info(f"  {line}")

    cm = confusion_matrix(y_te, y_pred, labels=all_label_ids)
    fig, ax = plt.subplots(figsize=(5, 4))
    ConfusionMatrixDisplay(
        cm,
        display_labels=[str(c) for c in pre["encoder"].classes_]
    ).plot(cmap="Blues", values_format="d", ax=ax, colorbar=False)
    ax.set_title(f"Confusion matrix --- SVM --- {task}")
    fig.tight_layout()
    out = FIGS_DIR / f"cm_svm_{task}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info(f"  Saved {out}")


# Step 3: permutation importance
def perm_importance(model, X_te, y_te, feature_names, task, n_repeats=20):
    r = permutation_importance(model, X_te, y_te,
                               n_repeats=n_repeats, random_state=42,
                               n_jobs=-1)
    order = np.argsort(r.importances_mean)[::-1]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.boxplot(r.importances[order].T,
               tick_labels=[feature_names[i] for i in order])
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_ylabel("accuracy drop when shuffled")
    ax.set_title(f"Permutation importance --- SVM --- {task}")
    fig.tight_layout()
    out = FIGS_DIR / f"perm_importance_svm_{task}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info(f"  Saved {out}")
    ranking = []
    for i in order:
        log.info(f"    {feature_names[i]:20s}  "
                 f"mean={r.importances_mean[i]:+.3f}  "
                 f"std={r.importances_std[i]:.3f}")
        ranking.append((feature_names[i], float(r.importances_mean[i]),
                        float(r.importances_std[i])))
    return ranking


for task, res in results.items():
    if res.get("skipped"):
        continue
    pkl = joblib.load(ARTIFACTS_DIR / task / "svm.pkl")
    _, _, _, _, X_te, y_te, pre = load_task(task)
    log.info(f"--- {task} permutation importance (SVM) ---")
    res["perm_importance"] = perm_importance(
        pkl["model"], X_te, y_te, pre["feature_cols"], task)


# Step 4: cross-check against RF
if RF_MANIFEST.exists():
    with open(RF_MANIFEST) as f:
        rf_manifest = json.load(f).get("results", {})
else:
    log.warning("baselines_manifest.json not found --- "
                "skipping RF cross-check (run baselines.py first)")
    rf_manifest = {}

for task, res in results.items():
    if res.get("skipped"):
        continue
    rf_entry = rf_manifest.get(task)
    if not rf_entry or rf_entry.get("skipped"):
        continue
    rf_imp = rf_entry.get("feature_importance", [])
    if not rf_imp:
        continue
    rf_rank  = {name: r for r, (name, _) in enumerate(rf_imp)}
    svm_rank = {name: r for r, (name, _, _) in enumerate(res["perm_importance"])}
    common = sorted(set(rf_rank) & set(svm_rank))
    if len(common) < 2:
        log.warning(f"  {task}: too few shared features for rank correlation")
        continue
    rho, _ = spearmanr([rf_rank[c]  for c in common],
                       [svm_rank[c] for c in common])
    log.info(f"  {task}: RF Gini vs SVM perm rank correlation rho = {rho:+.2f}")
    res["rank_correlation_vs_rf"] = float(rho)


# Step 5: head-to-head summary
log.info("=== RF vs SVM Summary ===")
log.info(f"{'Task':<8} {'RF acc':>8} {'SVM acc':>8} {'delta':>8} "
         f"{'kernel':>8} {'rho_imp':>8}")
for task in ["sf", "mod", "beacon", "pkt"]:
    res = results[task]
    if res.get("skipped"):
        log.info(f"{task:<8} (skipped)  reason: {res['reason']}")
        continue
    rf_entry = rf_manifest.get(task, {}) or {}
    rf_rf    = rf_entry.get("rf") if not rf_entry.get("skipped") else None
    rf_acc   = rf_rf.get("acc") if rf_rf else None
    rf_str   = f"{rf_acc:>8.3f}" if rf_acc is not None else f"{'n/a':>8}"
    delta    = (res["test_acc"] - rf_acc) if rf_acc is not None else None
    delta_str = f"{delta:>+8.3f}" if delta is not None else f"{'n/a':>8}"
    rho      = res.get("rank_correlation_vs_rf")
    rho_str  = f"{rho:>+8.2f}"  if rho is not None else f"{'n/a':>8}"
    log.info(f"{task:<8} {rf_str} {res['test_acc']:>8.3f} {delta_str} "
             f"{str(res['kernel']):>8} {rho_str}")


manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_stamp":    run_stamp,
    "log_archive":  str(log_archive),
    "svm_grid":     SVM_GRID,
    "results":      results,
}
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, default=str)
log.info(f"Wrote {MANIFEST_PATH}")
log.info("=== svm_train.py done ===")
