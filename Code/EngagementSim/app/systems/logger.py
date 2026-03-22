"""Per-asset logging with timestamped rotation and CSV export.

Each asset gets its own sub-folder under the session log directory:
    logs/<session_ts>/
        _global/engagement.log, data_stream.log
        Target-Alpha/engagement.log, data_stream.log
        Threat-1/engagement.log, data_stream.log
        ...
"""

import csv
import os
import logging
from app.utils.helpers import timestamp, timestamp_filename


def _make_logger(name: str, path: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False
    fh = logging.FileHandler(path, mode="a")
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    return logger


class AssetLogger:
    """Logger scoped to a single asset."""

    def __init__(self, asset_name: str, folder: str, session_id: str):
        self.asset_name = asset_name
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

        uid = f"{session_id}_{asset_name}"
        self.eng_path = os.path.join(folder, "engagement.log")
        self.data_path = os.path.join(folder, "data_stream.log")
        self._eng = _make_logger(f"eng_{uid}", self.eng_path)
        self._data = _make_logger(f"data_{uid}", self.data_path)

    def event(self, message: str):
        self._eng.info(f"[{timestamp()}] [{self.asset_name}] {message}")

    def data_stream(self, dest: str, msg_type: str, sequence: str):
        self._data.info(
            f"[{timestamp()}] {self.asset_name} -> {dest} | {msg_type} | {sequence}")

    def shutdown(self):
        for lg in (self._eng, self._data):
            for h in lg.handlers[:]:
                h.close()
                lg.removeHandler(h)


class SimLogger:
    """Session-wide logger that also owns per-asset loggers."""

    def __init__(self, log_dir: str = "."):
        self.session_id = timestamp_filename()
        self.session_dir = os.path.join(log_dir, self.session_id)
        os.makedirs(self.session_dir, exist_ok=True)

        # Global (aggregate) logger
        self._global = AssetLogger("GLOBAL", os.path.join(self.session_dir, "_global"),
                                   self.session_id)

        # Per-asset loggers keyed by asset name
        self._asset_loggers: dict[str, AssetLogger] = {}

        # CSV export buffer
        self.csv_rows: list = []

        self.log_event("SYSTEM", "=== Engagement Simulator Started ===")

    # ----- per-asset logger management --------------------------------------
    def register_asset(self, name: str):
        if name not in self._asset_loggers:
            folder = os.path.join(self.session_dir, name.replace(" ", "_"))
            self._asset_loggers[name] = AssetLogger(name, folder, self.session_id)

    def _asset(self, name: str) -> AssetLogger | None:
        return self._asset_loggers.get(name)

    # ----- logging ----------------------------------------------------------
    def log_event(self, asset: str, message: str):
        line = f"[{timestamp()}] [{asset}] {message}"
        self._global._eng.info(line)
        al = self._asset(asset)
        if al:
            al.event(message)
        self.csv_rows.append({
            "timestamp": timestamp(), "asset": asset,
            "type": "EVENT", "message": message})

    def log_data_stream(self, source: str, dest: str, msg_type: str, sequence: str):
        line = f"[{timestamp()}] {source} -> {dest} | {msg_type} | {sequence}"
        self._global._data.info(line)
        for name in (source, dest):
            al = self._asset(name)
            if al:
                al.data_stream(dest if name == source else source, msg_type, sequence)
        self.csv_rows.append({
            "timestamp": timestamp(), "asset": source,
            "type": msg_type, "message": f"{source} -> {dest} | {sequence}"})

    # ----- export / clear ---------------------------------------------------
    def export_csv(self, path: str):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "asset", "type", "message"])
            writer.writeheader()
            writer.writerows(self.csv_rows)

    def clear_logs(self):
        # Truncate all log files
        for al in [self._global] + list(self._asset_loggers.values()):
            for p in (al.eng_path, al.data_path):
                with open(p, "w"):
                    pass
        self.csv_rows.clear()
        self.log_event("SYSTEM", "=== Logs Cleared ===")

    def shutdown(self):
        self.log_event("SYSTEM", "=== Engagement Simulator Stopped ===")
        self._global.shutdown()
        for al in self._asset_loggers.values():
            al.shutdown()
