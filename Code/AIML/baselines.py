"""LH4-C - Dummy, decision tree, and random forest baselines.

For each classification task with >=2 classes, fits a majority-class
DummyClassifier, a depth-5 DecisionTreeClassifier, and a grid-searched
RandomForestClassifier on the LH4-B preprocessed artifacts. Reports
test accuracy with a 95% Wilson confidence interval, plots feature
importance, and saves the winning forest plus a manifest.

Run:
    python baselines.py
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
from scipy.stats import norm
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GridSearchCV
from sklearn.tree import DecisionTreeClassifier

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
FIGS_DIR      = SCRIPT_DIR / "figs"
MANIFEST_PATH = SCRIPT_DIR / "baselines_manifest.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
FIGS_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"baselines_{run_stamp}.log"
log_latest  = LOG_DIR / "baselines_latest.log"

log = logging.getLogger("baselines")
log.setLevel(logging.DEBUG)
log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt)
    log.addHandler(h)

log.info("=== baselines.py starting ===")
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


def report_acc(label, y_true, y_pred):
    n = len(y_true)
    n_correct = int((y_pred == y_true).sum())
    acc = n_correct / n if n else 0.0
    lo, hi = wilson_ci(n_correct, n)
    log.info(f"  {label}: acc = {acc:.3f}  [95% CI {lo:.3f}, {hi:.3f}]  "
             f"({n_correct}/{n})")
    return {"acc": acc, "ci_lo": lo, "ci_hi": hi,
            "n_correct": n_correct, "n_total": n}


def plot_importance(model, feature_names, task):
    imp = model.feature_importances_
    order = np.argsort(imp)[::-1]
    plt.figure(figsize=(7, 3.5))
    plt.bar(range(len(imp)), imp[order], color="steelblue")
    plt.xticks(range(len(imp)),
               [feature_names[i] for i in order], rotation=30, ha="right")
    plt.ylabel("Gini importance")
    plt.title(f"Random Forest feature importance --- task: {task}")
    plt.tight_layout()
    out = FIGS_DIR / f"rf_importance_{task}.png"
    plt.savefig(out, dpi=150)
    plt.close()
    log.info(f"  Saved {out}")
    return [(feature_names[i], float(imp[i])) for i in order]


RF_GRID = {
    "n_estimators":     [100, 300, 600],
    "max_depth":        [None, 10, 20],
    "min_samples_leaf": [1, 3],
    "max_features":     ["sqrt", "log2"],
}
n_combos = (len(RF_GRID["n_estimators"]) * len(RF_GRID["max_depth"])
            * len(RF_GRID["min_samples_leaf"]) * len(RF_GRID["max_features"]))
log.info(f"RF grid: {n_combos} hyperparameter combos x 5 folds = "
         f"{n_combos * 5} fits per task")


results = {}
for task in ["sf", "mod", "beacon", "pkt"]:
    log.info(f"--- Task: {task} ---")
    X_tr, y_tr, X_va, y_va, X_te, y_te, pre = load_task(task)
    n_classes = len(np.unique(y_tr))
    log.info(f"  Train shape={X_tr.shape}, classes={n_classes}, "
             f"features={pre['feature_cols']}")
    if n_classes < 2:
        log.warning(f"  {task}: only {n_classes} class --- "
                    f"skipping (Dummy/Tree/RF undefined for one class)")
        results[task] = {"skipped": True,
                         "reason": f"only {n_classes} class in train"}
        continue

    # Rung 1: Dummy
    dum = DummyClassifier(strategy="most_frequent", random_state=42)
    dum.fit(X_tr, y_tr)
    dum_res = report_acc("Dummy ", y_te, dum.predict(X_te))

    # Rung 2: Single decision tree, depth 5
    dt = DecisionTreeClassifier(max_depth=5, random_state=42)
    dt.fit(X_tr, y_tr)
    dt_res = report_acc("Tree-5", y_te, dt.predict(X_te))

    # Rung 3: Random forest grid search on train+val.
    X_cv = np.concatenate([X_tr, X_va]); y_cv = np.concatenate([y_tr, y_va])
    rf = RandomForestClassifier(random_state=42, n_jobs=-1)
    log.info(f"  Running RF grid search ({n_combos * 5} fits)...")
    gs = GridSearchCV(rf, RF_GRID, cv=5, scoring="accuracy",
                      n_jobs=-1, verbose=0)
    gs.fit(X_cv, y_cv)
    best = gs.best_estimator_
    rf_res = report_acc("RF best", y_te, best.predict(X_te))
    rf_res["cv_acc"] = float(gs.best_score_)
    rf_res["params"] = gs.best_params_
    log.info(f"  RF best params: {gs.best_params_}")
    log.info(f"  RF CV acc = {gs.best_score_:.3f}")

    # Save winning forest.
    joblib.dump({"model": best, **rf_res},
                ARTIFACTS_DIR / task / "rf.pkl")
    log.info(f"  Saved {ARTIFACTS_DIR / task / 'rf.pkl'}")

    # Feature importance.
    ranking = plot_importance(best, pre["feature_cols"], task)
    log.info(f"  Top features: "
             f"{', '.join(f'{n}={v:.2f}' for n, v in ranking[:3])}")

    results[task] = {
        "dummy": dum_res, "tree5": dt_res, "rf": rf_res,
        "feature_cols":       pre["feature_cols"],
        "feature_importance": ranking,
    }


log.info("=== Baseline Summary ===")
log.info(f"{'Task':<8} {'Dummy':>10} {'Tree-5':>10} {'RF best':>10} "
         f"{'RF 95% CI':>22}")
for task in ["sf", "mod", "beacon", "pkt"]:
    res = results[task]
    if res.get("skipped"):
        log.info(f"{task:<8} {'(skipped)':>10}  reason: {res['reason']}")
        continue
    d = res["dummy"]["acc"]; t = res["tree5"]["acc"]; r = res["rf"]
    log.info(f"{task:<8} {d:>10.3f} {t:>10.3f} {r['acc']:>10.3f} "
             f"   [{r['ci_lo']:.3f}, {r['ci_hi']:.3f}]")


manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_stamp":    run_stamp,
    "log_archive":  str(log_archive),
    "rf_grid":      RF_GRID,
    "results":      results,
}
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, default=str)
log.info(f"Wrote {MANIFEST_PATH}")
log.info("=== baselines.py done ===")
