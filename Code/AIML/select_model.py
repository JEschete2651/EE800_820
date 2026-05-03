"""LH4-H - Final model-selection rubric driver.

Reads every LH4 manifest, runs a latency microbenchmark for each
candidate model, scores RF/SVM/MLP/CNN per task on a 0-5 scale across
five criteria (accuracy, robustness, latency, interpretability,
deployment complexity), applies the rubric weights, picks the winning
model per task, and writes deployment_manifest.json + an archived log.

Run:
    python select_model.py
"""
import json
import logging
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from inference import InferenceEngine

SCRIPT_DIR    = Path(__file__).parent
LOG_DIR       = SCRIPT_DIR / "Logs"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
DEPLOYMENT_PATH = SCRIPT_DIR / "deployment_manifest.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"select_model_{run_stamp}.log"
log_latest  = LOG_DIR / "select_model_latest.log"

log = logging.getLogger("select_model")
log.setLevel(logging.DEBUG); log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt); log.addHandler(h)

log.info("=== select_model.py starting ===")
log.info(f"Run stamp: {run_stamp}")
log.info(f"Archive log: {log_archive}")


WEIGHTS = {"acc": 0.40, "rob": 0.25, "lat": 0.15,
           "interp": 0.10, "complex": 0.10}
INTERP_FIXED  = {"rf": 5, "svm": 4, "mlp": 2, "cnn": 2}
COMPLEX_FIXED = {"rf": 5, "svm": 5, "mlp": 3, "cnn": 2}
TASKS = ["sf", "beacon", "pkt"]
CANDIDATES = ["rf", "svm", "mlp", "cnn"]
LATENCY_TARGET_MS = 8.0


def load_manifest(name):
    p = SCRIPT_DIR / name
    if not p.exists():
        log.error(f"Missing manifest: {name}")
        sys.exit(1)
    return json.loads(p.read_text())


def load_acc_per_task():
    rf  = load_manifest("baselines_manifest.json")["results"]
    svm = load_manifest("svm_manifest.json")["results"]
    mlp = load_manifest("mlp_manifest.json")["results"]
    cnn = load_manifest("cnn_manifest.json")["results"]
    out = {}
    for task in TASKS:
        rf_entry  = rf.get(task,  {}) or {}
        svm_entry = svm.get(task, {}) or {}
        mlp_entry = mlp.get(task, {}) or {}
        cnn_entry = cnn.get(task, {}) or {}
        out[task] = {
            "rf":  None if rf_entry.get("skipped")  else (rf_entry.get("rf")  or {}).get("acc"),
            "svm": None if svm_entry.get("skipped") else svm_entry.get("test_acc"),
            "mlp": None if mlp_entry.get("skipped") else mlp_entry.get("test_acc"),
            "cnn": None if cnn_entry.get("skipped") else cnn_entry.get("test_acc"),
        }
    return out


def load_robustness_per_task():
    s = load_manifest("stratified_manifest.json")
    return s.get("robustness", {})


def normalize_to_0_5(values):
    arr = np.asarray([v if v is not None else np.nan for v in values],
                     dtype=float)
    if np.all(np.isnan(arr)):
        return [0.0] * len(values)
    mn = np.nanmin(arr); mx = np.nanmax(arr)
    if mx == mn:
        return [5.0 if not np.isnan(v) else 0.0 for v in arr]
    return [5.0 * (v - mn) / (mx - mn) if not np.isnan(v) else 0.0
            for v in arr]


def latency_inverse_to_0_5(values):
    arr = np.asarray([v if v is not None else np.inf for v in values],
                     dtype=float)
    finite = arr[np.isfinite(arr)]
    if len(finite) == 0:
        return [0.0] * len(values)
    mn = finite.min(); mx = finite.max()
    if mx == mn:
        return [5.0 if np.isfinite(v) else 0.0 for v in arr]
    return [5.0 * (mx - v) / (mx - mn) if np.isfinite(v) else 0.0
            for v in arr]


def microbenchmark(model_kind, n_warmup=20, n_iter=1000):
    eng = InferenceEngine({t: model_kind for t in TASKS},
                          artifacts_dir=ARTIFACTS_DIR)
    cols = set()
    for pre in eng.prep.values():
        cols.update(pre["feature_cols"])
    feat = {c: 0.0 for c in cols}
    seq_buf = {t: deque([np.zeros(len(eng.prep[t]["feature_cols"]),
                                  dtype=np.float32) for _ in range(8)],
                        maxlen=8)
               for t in eng.models}
    for _ in range(n_warmup):
        eng.predict(feat, seq_buf)
    lats = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        eng.predict(feat, seq_buf)
        lats.append((time.perf_counter() - t0) * 1000.0)
    lats = np.asarray(lats)
    return {"median": float(np.median(lats)),
            "mean":   float(lats.mean()),
            "p95":    float(np.percentile(lats, 95)),
            "p99":    float(np.percentile(lats, 99)),
            "max":    float(lats.max())}


def score_per_task(accs, robs, lats):
    rows = {}
    for task, by_model in accs.items():
        acc_vec = [by_model.get(m) for m in CANDIDATES]
        rob_vec = [(robs.get(task, {}).get(m) or {}).get("min")
                   for m in CANDIDATES]
        lat_vec = [lats.get(m, {}).get("median") for m in CANDIDATES]
        a5 = normalize_to_0_5(acc_vec)
        r5 = normalize_to_0_5(rob_vec)
        l5 = latency_inverse_to_0_5(lat_vec)
        scores = {}
        for i, m in enumerate(CANDIDATES):
            total = (WEIGHTS["acc"]     * a5[i]
                     + WEIGHTS["rob"]     * r5[i]
                     + WEIGHTS["lat"]     * l5[i]
                     + WEIGHTS["interp"]  * INTERP_FIXED[m]
                     + WEIGHTS["complex"] * COMPLEX_FIXED[m])
            scores[m] = {"total": total,
                         "components": {"acc": a5[i], "rob": r5[i],
                                        "lat": l5[i],
                                        "interp": INTERP_FIXED[m],
                                        "complex": COMPLEX_FIXED[m]},
                         "raw": {"acc": acc_vec[i],
                                 "rob": rob_vec[i],
                                 "lat_ms": lat_vec[i]}}
        rows[task] = scores
    return rows


# Step 1: latency benchmark
log.info("=== Latency microbenchmark (1000 iter, warm) ===")
lats = {}
for m in CANDIDATES:
    bench = microbenchmark(m)
    lats[m] = bench
    flag = " [over budget!]" if bench["p99"] > LATENCY_TARGET_MS else ""
    log.info(f"  {m:<5} median={bench['median']:.3f}  "
             f"mean={bench['mean']:.3f}  "
             f"p95={bench['p95']:.3f}  p99={bench['p99']:.3f}  "
             f"max={bench['max']:.3f} ms{flag}")

# Step 2: read accuracies + robustness
accs = load_acc_per_task()
robs = load_robustness_per_task()

# Step 3: score and pick
log.info("=== Per-task rubric scores ===")
rows = score_per_task(accs, robs, lats)
choices = {}
for task in TASKS:
    log.info(f"--- {task} ---")
    scores = rows[task]
    ranked = sorted(scores.items(), key=lambda kv: -kv[1]["total"])
    for m, s in ranked:
        c = s["components"]; r = s["raw"]
        raw_acc = f"{r['acc']:.3f}" if r['acc'] is not None else "n/a"
        raw_rob = f"{r['rob']:.3f}" if r['rob'] is not None else "n/a"
        raw_lat = f"{r['lat_ms']:.3f}" if r['lat_ms'] is not None else "n/a"
        log.info(f"  {m:<5} total={s['total']:.3f}  "
                 f"|  acc={c['acc']:.2f}({raw_acc}) "
                 f"rob={c['rob']:.2f}({raw_rob}) "
                 f"lat={c['lat']:.2f}({raw_lat}ms) "
                 f"interp={c['interp']} complex={c['complex']}")
    choices[task] = ranked[0][0]
    log.info(f"  WINNER: {choices[task]} "
             f"(score {ranked[0][1]['total']:.3f})")

# Step 4: schema check
log.info("=== Schema-drift check ===")
val_manifest = load_manifest("validation_manifest.json")
training_schema = set(val_manifest["schema"])
needed = set()
for task, choice in choices.items():
    pre = joblib.load(ARTIFACTS_DIR / task / "preprocessor.pkl")
    needed.update(pre["feature_cols"])
missing = needed - training_schema
if missing:
    log.error(f"Schema drift: deployed models need columns {missing} "
              f"not present in validation_manifest.")
    sys.exit(1)
log.info(f"Schema check PASS: all {len(needed)} needed columns "
         f"present in validation_manifest.")

# Step 5: write deployment manifest
manifest = {
    "generated_at":     datetime.now(timezone.utc).isoformat(),
    "run_stamp":        run_stamp,
    "log_archive":      str(log_archive),
    "weights":          WEIGHTS,
    "latency_target_ms": LATENCY_TARGET_MS,
    "latency":          lats,
    "scores":           rows,
    "deployed_choice":  choices,
    "needed_columns":   sorted(needed),
}
DEPLOYMENT_PATH.write_text(json.dumps(manifest, indent=2, default=str))
log.info(f"Wrote {DEPLOYMENT_PATH}")
log.info(f"Deployed choice: {choices}")
log.info("=== select_model.py done ===")
