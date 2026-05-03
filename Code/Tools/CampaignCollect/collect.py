"""Module 3 campaign data collection.

Reads the Threat's 43-byte forwarding frames passed through the Nexys A7's
onboard USB-UART (ingest_top.vhd routes uart_rx_pin -> UART_RXD_OUT), parses
the embedded radio packet fields, attaches ground-truth labels from a
campaign configuration JSON, and appends one row per validated frame to a
CSV file.

Frame layout (matches Nucleo_RFM95_Threat build_forwarding_frame()):
    byte  0       0x7E start delimiter
    byte  1       0x29 length (covers bytes 1..41 for CRC)
    bytes 2..5    rx_timestamp_ms      (LE uint32)
    byte  6       rssi_dbm             (signed int8, raw -dBm)
    byte  7       snr_q025             (signed int8, 0.25 dB units)
    bytes 8..9    freq_error_hz        (LE int16)
    bytes 10..41  radio payload (32 B)
    byte  42      CRC-8/ITU over bytes 1..41

Usage:
    python collect.py
    (interactive menu — select config and COM port; output CSV is named
     automatically from the config and written to the same directory)
"""
import csv
import json
import sys
from datetime import datetime, timezone

import serial


BAUD            = 115200
FRAME_LEN       = 43
START           = 0x7E
LENGTH          = 0x29
STALE_TIMEOUT_S = 10


def crc8_itu(data, poly=0x07, init=0x00):
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


def parse_forwarding_frame(buf43):
    rx_ts_ms    = int.from_bytes(buf43[2:6],  "little")
    rssi_dbm    = int.from_bytes(buf43[6:7],  "little", signed=True)
    snr_q025    = int.from_bytes(buf43[7:8],  "little", signed=True)
    freq_err_hz = int.from_bytes(buf43[8:10], "little", signed=True)
    payload     = buf43[10:42]

    beacon_id     = payload[2]
    seq_num       = int.from_bytes(payload[3:5], "little")
    payload_len   = payload[5]
    mod_code      = payload[6]
    pkt_type      = mod_code & 0x03
    mod_kind      = (mod_code >> 2) & 0x3F
    spread_factor = payload[7]
    tx_ts_ms      = int.from_bytes(payload[9:13], "little")

    return {
        "rx_timestamp_ms": rx_ts_ms,
        "rssi_dbm":        rssi_dbm,
        "snr_db":          snr_q025 / 4.0,
        "freq_error_hz":   freq_err_hz,
        "beacon_id":       beacon_id,
        "seq_num":         seq_num,
        "payload_len":     payload_len,
        "mod_kind":        mod_kind,
        "spread_factor":   spread_factor,
        "pkt_type":        pkt_type,
        "tx_timestamp_ms": tx_ts_ms,
    }


CSV_COLUMNS = [
    "campaign_id", "run_id", "timestamp_host",
    "rx_timestamp_ms", "tx_timestamp_ms", "inter_arrival_ms",
    "beacon_id", "seq_num", "pkt_type", "mod_kind", "spread_factor",
    "rssi_dbm", "snr_db", "freq_error_hz", "payload_len",
    "distance_m", "label_sf", "label_mod", "mod_kind_label",
    "label_beacon", "label_pkt",
]


def collect(port, config_path, out_csv):
    with open(config_path) as f:
        cfg = json.load(f)
    target        = cfg["target_packets"]
    duration_s    = cfg.get("collection_duration_s")   # None = packet-count mode
    received      = 0
    last_rx_ts    = None

    print(f"  Config : {cfg.get('description', cfg['run_id'])}")
    print(f"  Output : {out_csv}")
    print()
    print("  Ensure Target A, Threat, and FPGA are all powered and running.")
    input("  Press Enter to begin collection... ")

    with serial.Serial(port, BAUD, timeout=2.0) as ser, \
         open(out_csv, "w", newline="") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        ser.reset_input_buffer()

        if duration_s:
            print(f"Collecting for {duration_s}s (up to {target} packets) for "
                  f"{cfg['campaign_id']} sweep={cfg.get('sweep_value', '?')}...")
        else:
            print(f"Collecting {target} packets for {cfg['campaign_id']} "
                  f"sweep={cfg.get('sweep_value', '?')}...")

        collect_start    = datetime.now(timezone.utc)
        last_frame_time  = collect_start
        last_heartbeat   = collect_start

        def _deadline_reached(now):
            if duration_s and (now - collect_start).total_seconds() >= duration_s:
                return True
            return received >= target

        while not _deadline_reached(datetime.now(timezone.utc)):
            b = ser.read(1)
            now = datetime.now(timezone.utc)
            if not b:
                if _deadline_reached(now):
                    break
                stale = (now - last_frame_time).total_seconds()
                if stale >= STALE_TIMEOUT_S:
                    print(f"\n  [WARN] No valid frame received for {int(stale)}s.")
                    ans = input("  Continue waiting? [Y/n]: ").strip().lower()
                    if ans == "n":
                        break
                    last_frame_time = now
                elif (now - last_heartbeat).total_seconds() >= 2:
                    elapsed_s = (now - collect_start).total_seconds()
                    if duration_s:
                        rem = max(0, duration_s - elapsed_s)
                        print(f"  Waiting for frames... ({received} so far | "
                              f"{int(rem)}s remaining)")
                    else:
                        print(f"  Waiting for frames... ({received}/{target} so far)")
                    last_heartbeat = now
                continue
            if b[0] != START:
                continue
            length = ser.read(1)
            if not length or length[0] != LENGTH:
                continue
            rest = ser.read(FRAME_LEN - 2)
            if len(rest) < FRAME_LEN - 2:
                continue
            buf = bytes([START, LENGTH]) + rest

            expected_crc = crc8_itu(buf[1:42])
            if expected_crc != buf[42]:
                print(f"\n  [WARN] CRC mismatch: got {buf[42]:#04x}, "
                      f"expected {expected_crc:#04x}")
                continue

            last_frame_time = now
            last_heartbeat  = now
            fv = parse_forwarding_frame(buf)
            inter_arrival_ms = (fv["rx_timestamp_ms"] - last_rx_ts) \
                               if last_rx_ts is not None else 0
            last_rx_ts = fv["rx_timestamp_ms"]

            if fv["spread_factor"] != cfg["fixed_sf"]:
                print(f"\n  [WARN] SF mismatch: reported {fv['spread_factor']}, "
                      f"config {cfg['fixed_sf']}")
            if fv["pkt_type"] not in cfg.get("expected_pkt_types", [0, 1, 2]):
                print(f"\n  [WARN] unexpected pkt_type={fv['pkt_type']} "
                      f"(campaign expected {cfg.get('expected_pkt_types')})")

            row = {
                **fv,
                "inter_arrival_ms": inter_arrival_ms,
                "campaign_id":      cfg["campaign_id"],
                "run_id":           cfg["run_id"],
                "timestamp_host":   datetime.now(timezone.utc).isoformat(),
                "distance_m":       cfg["fixed_distance_m"],
                "label_sf":         cfg["fixed_sf"],
                "label_mod":        cfg["fixed_mod"],
                "mod_kind_label":   cfg["fixed_mod_kind"],
                "label_beacon":     fv["beacon_id"],
                "label_pkt":        fv["pkt_type"],
            }
            writer.writerow(row)
            received += 1

            elapsed_s = (now - collect_start).total_seconds()
            rate      = received / elapsed_s if elapsed_s > 0 else 0
            if duration_s:
                rem_s   = max(0, duration_s - elapsed_s)
                eta_str = f"{int(rem_s)}s remaining"
                count_str = f"{received} packets"
            else:
                remaining = target - received
                if rate > 0 and received >= 2:
                    eta_s   = int(remaining / rate)
                    eta_str = f"ETA {eta_s//60}m{eta_s%60:02d}s"
                else:
                    eta_str = "ETA --"
                count_str = f"{received}/{target} packets"
            print(f"  {count_str}  |  {rate:.2f} pkt/s  |  {eta_str}")

    print(f"\nDone. {received} packets written to {out_csv}.")


def _discover_configs():
    from pathlib import Path
    campaigns_dir = Path(__file__).parent / "campaigns"
    entries = []
    for p in sorted(campaigns_dir.glob("*.json")):
        try:
            with open(p) as f:
                cfg = json.load(f)
            entries.append((p, cfg.get("description", cfg.get("notes", p.stem))))
        except Exception:
            pass
    return entries


def _menu():
    configs = _discover_configs()
    if not configs:
        print("No JSON config files found in script directory.")
        sys.exit(1)

    print("\n=== Campaign Collect ===")
    print("Available configurations:\n")
    for i, (path, desc) in enumerate(configs, 1):
        print(f"  {i:2d}.  {desc}")
        print(f"       ({path.name})")
    print()

    while True:
        try:
            choice = input("Select config number: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(configs):
                config_path = configs[idx][0]
                break
            print(f"  Enter a number between 1 and {len(configs)}.")
        except (ValueError, EOFError):
            print("  Invalid input.")

    port = input("FPGA USB-UART COM port (e.g. COM3 or just 3): ").strip()
    if not port:
        print("No port entered.")
        sys.exit(1)
    if port.isdigit():
        port = f"COM{port}"

    from pathlib import Path
    script_dir = Path(__file__).parent
    log_dir = script_dir / "logs" / config_path.stem
    log_dir.mkdir(parents=True, exist_ok=True)
    out_csv = log_dir / f"results_{config_path.stem}.csv"

    print()
    collect(port, str(config_path), str(out_csv))


if __name__ == "__main__":
    _menu()
