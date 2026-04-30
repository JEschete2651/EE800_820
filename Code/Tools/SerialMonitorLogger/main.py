import csv
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QCloseEvent, QDesktopServices, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


MAX_VISIBLE_LINES = 5000
PORT_REFRESH_MS = 1500
DEFAULT_BAUD = 115200
QT_USER_ROLE = 32


class SerialReaderWorker(QObject):
    line_received = pyqtSignal(str, str)
    status_changed = pyqtSignal(str, str)
    bytes_received = pyqtSignal(str, int)
    error_occurred = pyqtSignal(str, str)
    finished = pyqtSignal(str)

    def __init__(self, port_name: str, baud_rate: int, timeout_s: float, log_file_path: Optional[Path]):
        super().__init__()
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.timeout_s = timeout_s
        self.log_file_path = log_file_path
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _emit_line(self, text: str, writer, log_file: Optional[TextIO]) -> None:
        self.line_received.emit(self.port_name, text)
        if writer is not None and log_file is not None:
            writer.writerow([datetime.now().isoformat(timespec="milliseconds"), self.port_name, text])
            log_file.flush()

    def run(self) -> None:
        ser = None
        log_file = None
        writer = None
        line_buffer = bytearray()

        try:
            self.status_changed.emit(self.port_name, "Opening serial port...")
            ser = serial.Serial(self.port_name, self.baud_rate, timeout=self.timeout_s)
            self.status_changed.emit(self.port_name, f"Monitoring at {self.baud_rate} baud")

            if self.log_file_path is not None:
                self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
                log_file = open(self.log_file_path, "w", newline="", encoding="utf-8")
                writer = csv.writer(log_file)
                writer.writerow(["timestamp", "port", "line"])
                log_file.flush()

            while not self._stop_event.is_set():
                chunk = ser.read(ser.in_waiting or 1)
                if not chunk:
                    continue

                self.bytes_received.emit(self.port_name, len(chunk))
                line_buffer.extend(chunk)

                while True:
                    newline_idx = line_buffer.find(b"\n")
                    if newline_idx < 0:
                        break

                    raw_line = line_buffer[:newline_idx]
                    del line_buffer[: newline_idx + 1]
                    text = raw_line.rstrip(b"\r").decode("utf-8", errors="replace")
                    self._emit_line(text, writer, log_file)

            if line_buffer:
                text = bytes(line_buffer).rstrip(b"\r\n").decode("utf-8", errors="replace")
                if text:
                    self._emit_line(text, writer, log_file)

            self.status_changed.emit(self.port_name, "Stopped")
        except Exception as exc:
            self.error_occurred.emit(self.port_name, f"{type(exc).__name__}: {exc}")
        finally:
            try:
                if log_file is not None:
                    log_file.flush()
                    log_file.close()
            except Exception:
                pass

            try:
                if ser is not None and ser.is_open:
                    ser.close()
            except Exception:
                pass

            self.finished.emit(self.port_name)


@dataclass
class PortPanel:
    container: QWidget
    output: QPlainTextEdit
    status_label: QLabel
    bytes_label: QLabel
    log_label: QLabel


@dataclass
class ActiveSession:
    thread: QThread
    worker: SerialReaderWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Monitor Logger")
        self.resize(1280, 760)

        self.base_dir = Path(__file__).resolve().parent
        self.log_dir = self.base_dir / "logs"

        self.panels_by_port: dict[str, PortPanel] = {}
        self.active_sessions: dict[str, ActiveSession] = {}
        self.total_bytes_by_port: dict[str, int] = {}

        self._build_ui()
        self.refresh_ports()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(PORT_REFRESH_MS)
        self.refresh_timer.timeout.connect(self.refresh_ports)
        self.refresh_timer.start()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(main_splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        port_group = QGroupBox("Available COM Ports")
        port_layout = QVBoxLayout(port_group)
        self.port_list = QListWidget()
        self.port_list.setSelectionMode(QListWidget.ExtendedSelection)
        port_layout.addWidget(self.port_list)

        settings_group = QGroupBox("Connection Settings")
        settings_layout = QGridLayout(settings_group)
        settings_layout.addWidget(QLabel("Baud"), 0, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.setEditable(True)
        for baud in [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]:
            self.baud_combo.addItem(str(baud))
        self.baud_combo.setCurrentText(str(DEFAULT_BAUD))
        settings_layout.addWidget(self.baud_combo, 0, 1)

        self.logging_checkbox = QCheckBox("Enable CSV logging")
        self.logging_checkbox.setChecked(True)
        settings_layout.addWidget(self.logging_checkbox, 1, 0, 1, 2)

        button_group = QGroupBox("Actions")
        button_layout = QVBoxLayout(button_group)

        self.refresh_btn = QPushButton("Refresh Ports")
        self.start_selected_btn = QPushButton("Start Selected")
        self.stop_selected_btn = QPushButton("Stop Selected")
        self.stop_all_btn = QPushButton("Stop All")
        self.clear_selected_btn = QPushButton("Clear Selected Output")
        self.open_logs_btn = QPushButton("Open Logs Folder")

        for btn in [
            self.refresh_btn,
            self.start_selected_btn,
            self.stop_selected_btn,
            self.stop_all_btn,
            self.clear_selected_btn,
            self.open_logs_btn,
        ]:
            button_layout.addWidget(btn)

        left_layout.addWidget(port_group)
        left_layout.addWidget(settings_group)
        left_layout.addWidget(button_group)
        left_layout.addStretch(1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.monitor_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.monitor_splitter.setChildrenCollapsible(False)
        right_layout.addWidget(self.monitor_splitter)

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([320, 960])

        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.start_selected_btn.clicked.connect(self.start_selected_ports)
        self.stop_selected_btn.clicked.connect(self.stop_selected_ports)
        self.stop_all_btn.clicked.connect(self.stop_all_ports)
        self.clear_selected_btn.clicked.connect(self.clear_selected_output)
        self.open_logs_btn.clicked.connect(self.open_logs_folder)

    def _current_baud(self) -> int:
        text = self.baud_combo.currentText().strip()
        try:
            baud = int(text)
            if baud <= 0:
                raise ValueError("Baud must be positive")
            return baud
        except Exception:
            QMessageBox.warning(self, "Invalid Baud", f"Invalid baud rate: {text}")
            self.baud_combo.setCurrentText(str(DEFAULT_BAUD))
            return DEFAULT_BAUD

    def _selected_ports(self) -> list[str]:
        devices: list[str] = []
        for item in self.port_list.selectedItems():
            device = item.data(QT_USER_ROLE)
            if device:
                devices.append(device)
        return devices

    def _sanitize_port_for_filename(self, port_name: str) -> str:
        safe = "".join(ch if ch.isalnum() else "_" for ch in port_name)
        return safe.strip("_") or "port"

    def _ensure_port_panel(self, port_name: str) -> PortPanel:
        existing = self.panels_by_port.get(port_name)
        if existing is not None:
            return existing

        container = QWidget()
        layout = QVBoxLayout(container)

        title_label = QLabel(f"Port: {port_name}")
        layout.addWidget(title_label)

        status_row = QHBoxLayout()
        status_label = QLabel("Status: Idle")
        bytes_label = QLabel("Bytes: 0")
        log_label = QLabel("Log: not active")
        status_row.addWidget(status_label)
        status_row.addWidget(bytes_label)
        status_row.addWidget(log_label)
        status_row.addStretch(1)

        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setLineWrapMode(QPlainTextEdit.NoWrap)

        layout.addLayout(status_row)
        layout.addWidget(output)

        self.monitor_splitter.addWidget(container)

        panel = PortPanel(
            container=container,
            output=output,
            status_label=status_label,
            bytes_label=bytes_label,
            log_label=log_label,
        )
        self.panels_by_port[port_name] = panel

        panel_count = len(self.panels_by_port)
        if panel_count > 0:
            self.monitor_splitter.setSizes([1] * panel_count)

        return panel

    def _remove_port_panel(self, port_name: str) -> None:
        panel = self.panels_by_port.pop(port_name, None)
        if panel is None:
            return
        panel.container.setParent(None)
        panel.container.deleteLater()

    def _trim_output(self, output: QPlainTextEdit) -> None:
        doc = output.document()
        if doc is None:
            return
        while doc.blockCount() > MAX_VISIBLE_LINES:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def refresh_ports(self) -> None:
        selected_before = set(self._selected_ports())
        available_ports = sorted(serial.tools.list_ports.comports(), key=lambda p: p.device)

        self.port_list.clear()
        for p in available_ports:
            device = p.device
            description = p.description or "Unknown"
            is_active = device in self.active_sessions

            label = f"{device} - {description}"
            if is_active:
                label += " [ACTIVE]"

            item = QListWidgetItem(label)
            item.setData(QT_USER_ROLE, device)
            if is_active:
                item.setForeground(QColor("darkgreen"))

            self.port_list.addItem(item)
            if device in selected_before:
                item.setSelected(True)

    def start_selected_ports(self) -> None:
        ports = self._selected_ports()
        if not ports:
            QMessageBox.information(self, "No Port Selected", "Select one or more COM ports first.")
            return

        baud = self._current_baud()
        enable_logging = self.logging_checkbox.isChecked()

        for port_name in ports:
            if port_name in self.active_sessions:
                continue

            panel = self._ensure_port_panel(port_name)
            self.total_bytes_by_port.setdefault(port_name, 0)
            panel.status_label.setText("Status: Starting...")

            log_path = None
            if enable_logging:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_port = self._sanitize_port_for_filename(port_name)
                log_path = self.log_dir / f"{safe_port}_{ts}.csv"
                panel.log_label.setText(f"Log: {log_path.name}")
            else:
                panel.log_label.setText("Log: disabled")

            thread = QThread(self)
            worker = SerialReaderWorker(port_name, baud, 0.2, log_path)
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.line_received.connect(self.on_line_received)
            worker.status_changed.connect(self.on_status_changed)
            worker.bytes_received.connect(self.on_bytes_received)
            worker.error_occurred.connect(self.on_error_occurred)
            worker.finished.connect(self.on_worker_finished)

            self.active_sessions[port_name] = ActiveSession(thread=thread, worker=worker)
            thread.start()

        self.refresh_ports()

    def stop_selected_ports(self) -> None:
        for port_name in self._selected_ports():
            self.stop_port(port_name)

    def stop_port(self, port_name: str) -> None:
        session = self.active_sessions.get(port_name)
        if session is None:
            return

        panel = self.panels_by_port.get(port_name)
        if panel is not None:
            panel.status_label.setText("Status: Stopping...")

        session.worker.stop()

    def stop_all_ports(self) -> None:
        for port_name in list(self.active_sessions.keys()):
            self.stop_port(port_name)

    def clear_selected_output(self) -> None:
        selected_ports = self._selected_ports()
        if not selected_ports:
            QMessageBox.information(self, "No Port Selected", "Select one or more COM ports to clear.")
            return

        for port_name in selected_ports:
            panel = self.panels_by_port.get(port_name)
            if panel is not None:
                panel.output.clear()
                self.total_bytes_by_port[port_name] = 0
                panel.bytes_label.setText("Bytes: 0")

    def open_logs_folder(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_dir)))

    def on_line_received(self, port_name: str, text: str) -> None:
        panel = self.panels_by_port.get(port_name)
        if panel is None:
            return
        panel.output.appendPlainText(text)
        self._trim_output(panel.output)

    def on_status_changed(self, port_name: str, status: str) -> None:
        panel = self.panels_by_port.get(port_name)
        if panel is not None:
            panel.status_label.setText(f"Status: {status}")

    def on_bytes_received(self, port_name: str, count: int) -> None:
        total = self.total_bytes_by_port.get(port_name, 0) + count
        self.total_bytes_by_port[port_name] = total

        panel = self.panels_by_port.get(port_name)
        if panel is not None:
            panel.bytes_label.setText(f"Bytes: {total}")

    def on_error_occurred(self, port_name: str, message: str) -> None:
        panel = self.panels_by_port.get(port_name)
        if panel is not None:
            panel.output.appendPlainText(f"[ERROR] {message}")
            panel.status_label.setText("Status: Error")

    def on_worker_finished(self, port_name: str) -> None:
        session = self.active_sessions.pop(port_name, None)
        if session is not None:
            session.thread.quit()
            session.thread.wait(2000)
            session.worker.deleteLater()
            session.thread.deleteLater()

        self._remove_port_panel(port_name)
        self.refresh_ports()

    def closeEvent(self, a0: Optional[QCloseEvent]) -> None:
        if a0 is None:
            return

        if self.active_sessions:
            choice = QMessageBox.question(
                self,
                "Stop Active Sessions",
                "There are active serial sessions. Stop all sessions and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if choice != QMessageBox.Yes:
                a0.ignore()
                return

            self.stop_all_ports()
            deadline = datetime.now().timestamp() + 3.0
            while self.active_sessions and datetime.now().timestamp() < deadline:
                QApplication.processEvents()

            for port_name, session in list(self.active_sessions.items()):
                try:
                    session.worker.stop()
                    session.thread.quit()
                    session.thread.wait(500)
                except Exception:
                    pass
                self.active_sessions.pop(port_name, None)

        a0.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
