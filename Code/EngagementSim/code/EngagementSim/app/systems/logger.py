"""Dual-file logging system for engagement events and data streams."""

import os
import logging
from app.utils.constants import ENGAGEMENT_LOG_FILE, DATA_STREAM_LOG_FILE
from app.utils.helpers import timestamp


class SimLogger:
    def __init__(self, log_dir: str = "."):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        self.engagement_path = os.path.join(log_dir, ENGAGEMENT_LOG_FILE)
        self.data_stream_path = os.path.join(log_dir, DATA_STREAM_LOG_FILE)

        # Set up Python loggers
        self._eng_logger = logging.getLogger("engagement")
        self._eng_logger.setLevel(logging.DEBUG)
        self._eng_logger.handlers.clear()
        eng_handler = logging.FileHandler(self.engagement_path, mode="a")
        eng_handler.setFormatter(logging.Formatter("%(message)s"))
        self._eng_logger.addHandler(eng_handler)

        self._data_logger = logging.getLogger("data_stream")
        self._data_logger.setLevel(logging.DEBUG)
        self._data_logger.handlers.clear()
        data_handler = logging.FileHandler(self.data_stream_path, mode="a")
        data_handler.setFormatter(logging.Formatter("%(message)s"))
        self._data_logger.addHandler(data_handler)

        self.log_event("SYSTEM", "=== Engagement Simulator Started ===")
        self.log_data_stream("SYSTEM", "SYSTEM", "INIT", "00000000")

    def log_event(self, asset: str, message: str):
        """Log an event to the engagement log file."""
        line = f"[{timestamp()}] [{asset}] {message}"
        self._eng_logger.info(line)

    def log_data_stream(self, source: str, dest: str, msg_type: str, sequence: str):
        """Log a binary data exchange to the data stream log file."""
        line = f"[{timestamp()}] {source} -> {dest} | {msg_type} | {sequence}"
        self._data_logger.info(line)

    def clear_logs(self):
        """Clear both log files."""
        for path in (self.engagement_path, self.data_stream_path):
            with open(path, "w") as f:
                f.write("")
        self.log_event("SYSTEM", "=== Logs Cleared ===")

    def shutdown(self):
        self.log_event("SYSTEM", "=== Engagement Simulator Stopped ===")
        for handler in self._eng_logger.handlers[:]:
            handler.close()
            self._eng_logger.removeHandler(handler)
        for handler in self._data_logger.handlers[:]:
            handler.close()
            self._data_logger.removeHandler(handler)
