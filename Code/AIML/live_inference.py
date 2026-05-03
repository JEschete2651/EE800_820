"""LH4-H Step 6 - Live serial-streaming inference (hardware demo).

Reads frames from the FPGA USB-UART, parses them with the LH3-F
helpers, and prints live predictions for the deployed models per task.
The deployed model choice is read from deployment_manifest.json.

Output goes to stdout AND to two log files (the standard AIML pattern):
    Logs/live_inference_<UTC stamp>.log   (archive of this run)
    Logs/live_inference_latest.log         (mirror of the most recent run)

Run (with hardware connected):
    python live_inference.py [COM_PORT] [DURATION_S]

Both args are optional and prompted interactively if missing
(LH3-F convention). DURATION_S can be:
    - a positive number (seconds) -> stop after that many seconds
    - 0 or empty                   -> run until Ctrl-C
Example:
    python live_inference.py 7 300    # COM7, stop after 5 minutes
    python live_inference.py 7 0      # COM7, run forever
"""
import json
import logging
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import serial

# Pull the LH3-F frame helpers from collect.py without re-running its menu.
sys.path.insert(0, str(Path(__file__).parent.parent / "Tools" / "CampaignCollect"))
from collect import (BAUD, FRAME_LEN, START, LENGTH,
                     crc8_itu, parse_forwarding_frame)

from inference import InferenceEngine

SCRIPT_DIR    = Path(__file__).parent
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"
DEPLOYMENT    = SCRIPT_DIR / "deployment_manifest.json"
LOG_DIR       = SCRIPT_DIR / "Logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

run_stamp   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
log_archive = LOG_DIR / f"live_inference_{run_stamp}.log"
log_latest  = LOG_DIR / "live_inference_latest.log"

log = logging.getLogger("live_inference")
log.setLevel(logging.DEBUG); log.handlers.clear()
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
for h in (logging.StreamHandler(sys.stdout),
          logging.FileHandler(log_archive, mode="w", encoding="utf-8"),
          logging.FileHandler(log_latest,  mode="w", encoding="utf-8")):
    h.setFormatter(fmt); log.addHandler(h)


def read_frame(ser):
    """Read one validated 43-byte frame; return the bytes or None."""
    b = ser.read(1)
    if not b or b[0] != START:
        return None
    length = ser.read(1)
    if not length or length[0] != LENGTH:
        return None
    rest = ser.read(FRAME_LEN - 2)
    if len(rest) < FRAME_LEN - 2:
        return None
    buf = bytes([START, LENGTH]) + rest
    if crc8_itu(buf[1:42]) != buf[42]:
        return None
    return buf


def main():
    log.info("=== live_inference.py starting ===")
    log.info(f"Run stamp: {run_stamp}")
    log.info(f"Archive log: {log_archive}")

    if not DEPLOYMENT.exists():
        log.error(f"Missing {DEPLOYMENT}. Run select_model.py first.")
        sys.exit(1)
    deployed = json.loads(DEPLOYMENT.read_text())
    choices = deployed["deployed_choice"]
    log.info(f"Deployed model choice: {choices}")

    eng = InferenceEngine(choices, artifacts_dir=ARTIFACTS_DIR)
    seq_buf = {t: deque([np.zeros(len(eng.prep[t]["feature_cols"]),
                                  dtype=np.float32) for _ in range(8)],
                        maxlen=8)
               for t in eng.models}

    if len(sys.argv) > 1:
        port = sys.argv[1].strip()
    else:
        port = input("FPGA USB-UART COM port (e.g. COM3 or just 3): ").strip()
    if port.isdigit():
        port = f"COM{port}"

    if len(sys.argv) > 2:
        dur_raw = sys.argv[2]
    else:
        dur_raw = input("Run duration in seconds (blank or 0 = until Ctrl-C): ").strip()
    try:
        duration_s = float(dur_raw) if dur_raw else 0.0
    except ValueError:
        log.error(f"Could not parse duration {dur_raw!r}; running until Ctrl-C.")
        duration_s = 0.0
    if duration_s > 0:
        log.info(f"Opening {port} @ {BAUD}; will stop after {duration_s:.1f}s.")
    else:
        log.info(f"Opening {port} @ {BAUD}; running until Ctrl-C.")

    deadline = (time.perf_counter() + duration_s) if duration_s > 0 else None
    last_rx_ts = None
    n_frames   = 0
    t_start    = time.perf_counter()
    try:
        with serial.Serial(port, BAUD, timeout=1.0) as ser:
            ser.reset_input_buffer()
            while True:
                if deadline is not None and time.perf_counter() >= deadline:
                    break
                buf = read_frame(ser)
                if buf is None:
                    continue
                fv = parse_forwarding_frame(buf)
                ia = (fv["rx_timestamp_ms"] - last_rx_ts) if last_rx_ts else 0
                last_rx_ts = fv["rx_timestamp_ms"]
                feat = {**fv, "inter_arrival_ms": ia,
                        # Scaled later per task; populate any other columns
                        # the preprocessors might want at zeros if absent.
                        "distance_m": 3.0, "payload_len": fv.get("payload_len", 14)}
                for t in eng.models:
                    cols = eng.prep[t]["feature_cols"]
                    row = np.asarray([feat[c] for c in cols], dtype=np.float32)
                    seq_buf[t].append(eng.prep[t]["scaler"].transform(
                        row.reshape(1, -1))[0])
                t0 = time.perf_counter()
                preds = eng.predict(feat, seq_buf)
                dt = (time.perf_counter() - t0) * 1000.0
                parts = []
                for t in ("sf", "beacon", "pkt"):
                    p = preds.get(t)
                    if p is None:
                        continue
                    pstr = (f"p={p['prob']:.2f}" if p['prob'] is not None
                            else "p=?")
                    parts.append(f"{t.upper()}={p['label']} ({pstr})")
                parts.append(f"lat={dt:.1f}ms")
                log.info(" | ".join(parts))
                n_frames += 1
    except KeyboardInterrupt:
        log.info("Ctrl-C received; stopping.")

    elapsed = time.perf_counter() - t_start
    rate = n_frames / elapsed if elapsed > 0 else 0.0
    log.info(f"=== Stopping: {n_frames} frames in {elapsed:.1f}s "
             f"({rate:.2f} fps) ===")


if __name__ == "__main__":
    main()
