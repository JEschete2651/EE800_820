"""LH1-G forwarding-frame parser.

Reads 43-byte frames from the Threat board's USART3 stream, validates the
frame CRC-8 (byte 42) and the embedded radio-packet CRC-16 (packet bytes
30..31), decodes the packed Modulation Code byte, and writes one CSV row
per valid frame.

Usage:
    python lh1g_parser.py <port> <baud> <out_csv>
    python lh1g_parser.py COM7 115200 LH1G_capture.csv
"""
import csv
import struct
import sys
from pathlib import Path

import serial


PKT_TYPE_NAMES = {0: "DATA", 1: "ACK", 2: "PAUSE", 3: "RESERVED"}
MOD_KIND_NAMES = {1: "LoRa", 2: "FSK", 3: "OOK"}

FRAME_LEN = 43
START_DELIM = 0x7E
LENGTH_FIELD = 0x29  # 41


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly=0x1021, init=0xFFFF, no reflect."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 \
                else (crc << 1) & 0xFFFF
    return crc


def crc8_itu(data: bytes) -> int:
    """CRC-8/ITU: poly=0x07, init=0x00, no reflect."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 \
                else (crc << 1) & 0xFF
    return crc


def parse_frame(buf: bytes) -> dict:
    """Validate one 43-byte frame; return decoded fields or {'error': ...}."""
    if len(buf) != FRAME_LEN or buf[0] != START_DELIM or buf[1] != LENGTH_FIELD:
        return {"error": "framing"}
    if crc8_itu(buf[1:42]) != buf[42]:
        return {"error": "frame_crc8"}

    rx_ts_ms = struct.unpack("<I", buf[2:6])[0]
    rssi = struct.unpack("b", buf[6:7])[0]
    snr_q025 = struct.unpack("b", buf[7:8])[0]
    freq_err = struct.unpack("<h", buf[8:10])[0]
    radio = buf[10:42]

    if crc16_ccitt(radio[:30]) != ((radio[30] << 8) | radio[31]):
        return {"error": "radio_crc16"}

    mod_byte = radio[6]
    mod_kind = (mod_byte >> 2) & 0x3F
    pkt_type = mod_byte & 0x03
    sender = radio[2]
    seq = radio[3] | (radio[4] << 8)

    return {
        "t_ms":     rx_ts_ms,
        "sender":   f"0x{sender:02X}",
        "pkt_type": PKT_TYPE_NAMES.get(pkt_type, f"?({pkt_type})"),
        "mod_kind": MOD_KIND_NAMES.get(mod_kind, f"?({mod_kind})"),
        "seq":      seq,
        "rssi":     rssi,
        "snr_db":   snr_q025 / 4.0,
        "freq_err": freq_err,
    }


def main(port: str, baud: int, out_csv: str) -> int:
    ser = serial.Serial(port, baud, timeout=0.2)
    fields = ["t_ms", "sender", "pkt_type", "mod_kind",
              "seq", "rssi", "snr_db", "freq_err"]
    n_ok = n_bad = 0

    print(f"Listening on {port} @ {baud} baud, writing {out_csv}",
          file=sys.stderr)

    with Path(out_csv).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        buf = bytearray()
        try:
            while True:
                buf += ser.read(64)
                while True:
                    i = buf.find(b"\x7E")
                    if i < 0:
                        buf.clear()
                        break
                    if i > 0:
                        del buf[:i]
                    if len(buf) < FRAME_LEN:
                        break
                    frame = bytes(buf[:FRAME_LEN])
                    del buf[:FRAME_LEN]
                    decoded = parse_frame(frame)
                    if "error" not in decoded:
                        writer.writerow(decoded)
                        f.flush()
                        n_ok += 1
                        print(decoded)
                    else:
                        n_bad += 1
                        print(f"DROP {decoded} raw={frame.hex()}",
                              file=sys.stderr)
        except KeyboardInterrupt:
            pass
        finally:
            ser.close()

    print(f"Parsed {n_ok} ok, {n_bad} dropped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: lh1g_parser.py <port> <baud> <out_csv>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1], int(sys.argv[2]), sys.argv[3]))
